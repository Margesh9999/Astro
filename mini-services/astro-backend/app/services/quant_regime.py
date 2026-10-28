"""
Risk & regime analytics (gs-quant risk, Q-Fin VaR, ffn drawdowns, OpenBB
`qa` menu, tf-quant-finance / QuantPy style simulation):
  * rolling volatility + rolling Sharpe (full history)
  * GARCH(1,1) volatility forecast (native scipy MLE)
  * Hurst exponent, full + rolling
  * 2-state Gaussian-mixture volatility regime (HMM-like)
  * Monte-Carlo price cone (block bootstrap) for ~30/60/90/365 days
  * VaR / CVaR — historical, parametric (normal), Cornish-Fisher
  * normality / unit-root / autocorrelation tests (JB, ADF, KPSS, Ljung-Box)
  * rolling beta / correlation / capture ratios vs a home benchmark
  * top-5 drawdown table (ffn drawdown details)
  * realised-volatility cone
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.signal import lfilter

from app.services.quant_common import BENCH_NAMES, clean, downsample, insight, naive, r
from app.services.quant_extra import _hurst_exponent

logger = logging.getLogger(__name__)
ANN = 252


# ── rolling vol / Sharpe ─────────────────────────────────────────────────────

def _rolling(ret: pd.Series) -> Dict:
    v21 = ret.rolling(21).std() * np.sqrt(ANN) * 100
    v63 = ret.rolling(63).std() * np.sqrt(ANN) * 100
    sh = ret.rolling(252).mean() / ret.rolling(252).std() * np.sqrt(ANN)
    keep = downsample(len(ret), 520)
    idx = ret.index[keep]
    sh_now = float(sh.iloc[-1]); sh_med = float(sh.median())
    v_now = float(v21.iloc[-1]); v_med = float(v21.median())
    pct_v = float((v21.dropna() < v_now).mean() * 100)
    return {
        "dates": [str(i.date()) for i in idx],
        "vol21": [r(v, 1) for v in v21.iloc[keep]], "vol63": [r(v, 1) for v in v63.iloc[keep]],
        "sharpe252": [r(v, 2) for v in sh.iloc[keep]],
        "vol_now": r(v_now, 1), "vol_median": r(v_med, 1), "vol_pctile": r(pct_v, 0),
        "sharpe_now": r(sh_now, 2), "sharpe_median": r(sh_med, 2),
        "insight": insight(
            "21- and 63-day annualised volatility and the trailing 1-year Sharpe ratio over the whole history.",
            f"Volatility is {v_now:.1f}% — higher than {pct_v:.0f}% of all days since {ret.index[0].year} (median {v_med:.1f}%). "
            f"The 1-year Sharpe is {sh_now:.2f} vs a long-run median of {sh_med:.2f}.",
            ("Calm and rewarding — the best backdrop for holding trend positions; keep normal size."
             if pct_v < 40 and sh_now > sh_med else
             "Stormy and unrewarding — cut size; this mix has historically preceded the deepest drawdowns."
             if pct_v > 75 and sh_now < sh_med else
             "Stormy but still rewarding — stay invested but trail stops more tightly."
             if pct_v > 75 else
             "Quiet but unrewarding — no hurry to add; wait for momentum to return."
             if sh_now < sh_med else
             "Normal conditions — standard sizing and playbooks apply."),
        ),
    }


# ── GARCH(1,1) ───────────────────────────────────────────────────────────────

def _garch_filter(params: np.ndarray, e2: np.ndarray, var0: float) -> np.ndarray:
    w, a, b = params
    x = w + a * np.concatenate([[var0], e2[:-1]])
    s2, _ = lfilter([1.0], [1.0, -b], x, zi=[b * var0])
    return s2


def _garch_nll(params: np.ndarray, e: np.ndarray, e2: np.ndarray, var0: float) -> float:
    w, a, b = params
    if w <= 0 or a < 0 or b < 0 or a + b >= 0.999:
        return 1e12
    s2 = _garch_filter(params, e2, var0)
    if np.any(s2 <= 0) or not np.all(np.isfinite(s2)):
        return 1e12
    return float(0.5 * np.sum(np.log(s2) + e2 / s2))


def fit_garch(ret: pd.Series, max_obs: int = 2520) -> Optional[Dict]:
    x = ret.dropna().iloc[-max_obs:] * 100
    if len(x) < 250:
        return None
    e = (x - x.mean()).to_numpy()
    e2 = e ** 2
    var0 = float(e2.mean())
    best = None
    for a0, b0 in ((0.08, 0.9), (0.05, 0.93), (0.15, 0.8)):
        w0 = var0 * (1 - a0 - b0)
        res = optimize.minimize(_garch_nll, np.array([w0, a0, b0]), args=(e, e2, var0),
                                method="Nelder-Mead", options={"maxiter": 2000, "xatol": 1e-7, "fatol": 1e-7})
        if best is None or res.fun < best.fun:
            best = res
    w, a, b = best.x
    s2 = _garch_filter(best.x, e2, var0)
    next_var = w + a * e2[-1] + b * s2[-1]
    persist = a + b
    vl = w / (1 - persist) if persist < 1 else var0
    hs = np.arange(1, 64)
    fvar = vl + persist ** (hs - 1) * (next_var - vl)
    term = [float(np.sqrt(fvar[:h].mean() * ANN)) for h in hs]
    keep = x.index >= x.index.max() - pd.Timedelta(days=730)
    cond = pd.Series(np.sqrt(s2 * ANN), index=x.index)[keep]
    real = (x.rolling(21).std() * np.sqrt(ANN))[keep]
    ds = downsample(len(cond), 260)
    half_life = float(np.log(0.5) / np.log(persist)) if 0 < persist < 1 else None
    now_v, lr_v = float(np.sqrt(next_var * ANN)), float(np.sqrt(vl * ANN))
    return {
        "omega": r(w, 5), "alpha": r(a, 4), "beta": r(b, 4), "persistence": r(persist, 4),
        "half_life_days": r(half_life, 0), "vol_next_day": r(now_v, 1), "vol_long_run": r(lr_v, 1),
        "vol_1m": r(term[20], 1), "vol_3m": r(term[62], 1),
        "term": [{"h": int(h), "vol": r(v, 2)} for h, v in zip(hs, term)],
        "history": {"dates": [str(i.date()) for i in cond.index[ds]],
                    "garch": [r(v, 1) for v in cond.iloc[ds]], "realised": [r(v, 1) for v in real.iloc[ds]]},
        "insight": insight(
            "GARCH(1,1) fitted by maximum likelihood on the last ~10 years: conditional volatility vs realised, and the forecast term structure.",
            f"Model vol for tomorrow is {now_v:.1f}% annualised vs a long-run level of {lr_v:.1f}%. Shocks fade with a half-life of "
            f"~{half_life:.0f} trading days (persistence {persist:.3f}), so 1-month expected vol is {term[20]:.1f}% and 3-month {term[62]:.1f}%."
            if half_life else f"Model vol for tomorrow is {now_v:.1f}% annualised.",
            ("Shocks here are extremely persistent (half-life > 1 year) — today's volatility level is the best guess for months ahead; "
             "size positions to the current level rather than waiting for calm."
             if half_life and half_life > 250 else
             "Vol is above its anchor and should drift DOWN — option premium is rich; favour selling premium with defined risk."
             if now_v > lr_v * 1.1 else
             "Vol is below its anchor and should drift UP — options are cheap; buying protection or long-vol spreads is good value."
             if now_v < lr_v * 0.9 else
             "Vol sits at its long-run anchor — no volatility edge either way; size by ATR as usual."),
        ),
    }


# ── Hurst ────────────────────────────────────────────────────────────────────

def _hurst(close: pd.Series) -> Dict:
    h_full = _hurst_exponent(close.iloc[-2520:])
    win, step = 504, 21
    c = close.iloc[-(2520 + win):]
    pts = []
    for end in range(win, len(c) + 1, step):
        seg = c.iloc[end - win:end]
        pts.append((c.index[end - 1], _hurst_exponent(seg)))
    if pts and pts[-1][0] != c.index[-1]:
        pts.append((c.index[-1], _hurst_exponent(c.iloc[-win:])))
    h_now = pts[-1][1] if pts else h_full
    reg = "trending" if h_now > 0.55 else "mean-reverting" if h_now < 0.45 else "random-walk"
    return {
        "full": r(h_full, 3), "now": r(h_now, 3), "regime": reg,
        "series": {"dates": [str(d.date()) for d, _ in pts], "hurst": [r(v, 3) for _, v in pts]},
        "insight": insight(
            "Hurst exponent (rescaled-range) on rolling 2-year windows. 0.5 = coin-flip, above = trends persist, below = moves reverse.",
            f"Current Hurst {h_now:.2f} → {reg} behaviour (10-year value {h_full:.2f}).",
            ("Trends persist: use breakout / moving-average rules from the Signals tab and let winners run."
             if reg == "trending" else
             "Moves tend to reverse: favour z-score / RSI / Bollinger mean-reversion rules and take profits quickly."
             if reg == "mean-reverting" else
             "No memory to exploit: timing rules add little — rely on diversification and position sizing."),
        ),
    }


# ── 2-state Gaussian mixture regime ─────────────────────────────────────────

def _regime(close: pd.Series, ret: pd.Series) -> Optional[Dict]:
    try:
        from sklearn.mixture import GaussianMixture
    except Exception:  # pragma: no cover
        return None
    lv = np.log(ret.rolling(21).std() * np.sqrt(ANN))
    r21 = close.pct_change(21)
    feat = pd.DataFrame({"lv": lv, "r21": r21}).dropna().iloc[-5040:]
    if len(feat) < 500:
        return None
    X = ((feat - feat.mean()) / feat.std()).to_numpy()
    gm = GaussianMixture(n_components=2, covariance_type="full", random_state=7, n_init=2).fit(X)
    post = gm.predict_proba(X)
    stress = int(np.argmax(gm.means_[:, 0]))
    p_stress = pd.Series(post[:, stress], index=feat.index).rolling(5, min_periods=1).mean()
    lab = (p_stress > 0.5).astype(int)
    fwd20 = (close.shift(-20) / close - 1).reindex(feat.index)
    dret = ret.reindex(feat.index)
    states = []
    for sid, nm in ((0, "Calm"), (1, "Stressed")):
        m = lab == sid
        runs = (m != m.shift()).cumsum()[m]
        dur = float(runs.value_counts().mean()) if m.any() else 0.0
        states.append({
            "name": nm, "share_pct": r(m.mean() * 100, 0),
            "ann_return_pct": r(dret[m].mean() * ANN * 100, 1) if m.any() else None,
            "ann_vol_pct": r(dret[m].std() * np.sqrt(ANN) * 100, 1) if m.any() else None,
            "fwd20_pct": r(fwd20[m].mean() * 100, 2) if m.any() else None,
            "avg_duration_days": r(dur, 0),
        })
    prev = lab.shift(1)
    p_cc = float(((prev == 0) & (lab == 0)).sum() / max(1, (prev == 0).sum()))
    p_ss = float(((prev == 1) & (lab == 1)).sum() / max(1, (prev == 1).sum()))
    now = float(p_stress.iloc[-1])
    tail = p_stress.index >= p_stress.index.max() - pd.Timedelta(days=3 * 365)
    ds = downsample(int(tail.sum()), 300)
    ps = p_stress[tail].iloc[ds]
    cp = close.reindex(ps.index)
    cur = "Stressed" if now > 0.5 else "Calm"
    s_calm, s_str = states
    return {
        "current": cur, "p_stress": r(now * 100, 0), "states": states,
        "stay_prob": {"calm": r(p_cc * 100, 1), "stressed": r(p_ss * 100, 1)},
        "series": {"dates": [str(i.date()) for i in ps.index], "p_stress": [r(v * 100, 1) for v in ps],
                   "close": [r(v, 2) for v in cp]},
        "insight": insight(
            "A 2-state Gaussian mixture (HMM-like) on 21-day volatility and 21-day return labels each day Calm or Stressed; the line is the probability of Stress.",
            f"Today is {cur} ({now*100:.0f}% stress probability). Historically Calm days returned {s_calm['ann_return_pct']}%/yr at "
            f"{s_calm['ann_vol_pct']}% vol and Stressed days {s_str['ann_return_pct']}%/yr at {s_str['ann_vol_pct']}% vol; "
            f"a Stressed spell lasts ~{s_str['avg_duration_days']:.0f} days on average.",
            ("Stress regime — halve leverage, widen stops, prefer hedged or defined-risk positions until probability drops below 50%."
             if cur == "Stressed" else
             "Calm regime — conditions favour holding trend positions; watch for the stress probability crossing 50% as an early exit warning."),
        ),
    }


# ── Monte-Carlo price cone ───────────────────────────────────────────────────

def _mc_cone(close: pd.Series, ret: pd.Series, paths: int = 2000, horizon: int = 252, block: int = 5) -> Dict:
    lr = np.log1p(ret.dropna().iloc[-2520:].to_numpy())
    n = len(lr)
    rng = np.random.default_rng(42)
    nb = int(np.ceil(horizon / block))
    starts = rng.integers(0, n - block, size=(paths, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(paths, -1)[:, :horizon]
    cum = np.cumsum(lr[idx], axis=1)
    last = float(close.iloc[-1])
    px = last * np.exp(cum)
    qs = [5, 25, 50, 75, 95]
    pct = np.percentile(px, qs, axis=0)
    steps = list(range(4, horizon, 5)) + [horizon - 1]
    cone = [{"day": int(s + 1), **{f"p{q}": r(pct[i, s], 2) for i, q in enumerate(qs)}} for s in steps]
    running_min = np.minimum.accumulate(px, axis=1)
    hz = []
    for lab, h in (("~30 days", 21), ("~60 days", 42), ("~90 days", 63), ("~1 year", 252)):
        col = px[:, h - 1]
        hz.append({
            "label": lab, "days": h,
            **{f"p{q}": r(np.percentile(col, q), 2) for q in qs},
            "prob_up": r((col > last).mean() * 100, 0),
            "prob_dd10": r((running_min[:, h - 1] < last * 0.9).mean() * 100, 0),
        })
    y = hz[-1]
    return {
        "last": r(last, 2), "paths": paths, "cone": cone, "horizons": hz,
        "insight": insight(
            f"{paths:,} simulated 1-year paths built by re-sampling 5-day blocks of the last 10 years of real returns (keeps fat tails and volatility clusters).",
            f"In 1 year the middle 50% of paths land between {y['p25']:,.2f} and {y['p75']:,.2f} (median {y['p50']:,.2f}); "
            f"{y['prob_up']:.0f}% finish above today and {y['prob_dd10']:.0f}% suffer a ≥10% dip along the way.",
            f"Plan for the 5% path ({y['p5']:,.2f}) when sizing: only commit capital you could hold through that outcome. "
            "These are modelled ranges, never promises.",
        ),
    }


# ── VaR / CVaR ───────────────────────────────────────────────────────────────

def _var_table(ret: pd.Series, notional: float = 10_000.0) -> Dict:
    x = ret.dropna().iloc[-1260:].to_numpy()
    mu, sd = float(x.mean()), float(x.std(ddof=1))
    s, k = float(stats.skew(x)), float(stats.kurtosis(x))
    rows = []
    for conf in (0.95, 0.99):
        a = 1 - conf
        z = stats.norm.ppf(a)
        zcf = z + (z ** 2 - 1) * s / 6 + (z ** 3 - 3 * z) * k / 24 - (2 * z ** 3 - 5 * z) * s ** 2 / 36
        hist = -np.percentile(x, a * 100)
        hist_es = -x[x <= -hist].mean()
        par = -(mu + z * sd)
        par_es = -(mu - sd * stats.norm.pdf(z) / a)
        cf = -(mu + zcf * sd)
        for h in (1, 10):
            sc = np.sqrt(h)
            rows.append({
                "conf": int(conf * 100), "horizon_days": h,
                "hist_var": r(hist * sc * 100, 2), "hist_cvar": r(hist_es * sc * 100, 2),
                "param_var": r(par * sc * 100, 2), "param_cvar": r(par_es * sc * 100, 2),
                "cf_var": r(cf * sc * 100, 2),
                "hist_var_amt": r(hist * sc * notional, 0), "cf_var_amt": r(cf * sc * notional, 0),
            })
    r95 = rows[0]; r99 = rows[2]
    gap = (r99["cf_var"] or 0) - (r99["param_var"] or 0)
    return {
        "rows": rows, "skew": r(s, 2), "excess_kurtosis": r(k, 2), "obs": int(len(x)), "notional": notional,
        "insight": insight(
            "Value-at-Risk (loss not exceeded on 95%/99% of days) and CVaR (average loss on the days that DO exceed it), "
            "three ways, from the last 5 years. Illustrative £/$10,000 position.",
            f"On a typical bad day (95%) expect to lose about {r95['hist_var']:.2f}% (≈{r95['hist_var_amt']:,.0f} per 10,000); "
            f"when it goes wrong the average loss is {r95['hist_cvar']:.2f}%. At 99%, the fat-tail-aware Cornish-Fisher VaR is "
            f"{r99['cf_var']:.2f}% vs {r99['param_var']:.2f}% from the bell curve"
            + (" — the bell curve understates the tail risk here." if gap > 0.1 else "."),
            f"Size positions so that a {r99['hist_cvar']:.1f}% day (99% CVaR) costs no more than ~1% of your total portfolio: "
            f"i.e. keep this holding below {min(100, 100 / max(r99['hist_cvar'] or 1, 0.1)):.0f}% of capital.",
        ),
    }


# ── statistical tests (OpenBB quantitative menu) ─────────────────────────────

def _tests(close: pd.Series, ret: pd.Series) -> Dict:
    x = ret.dropna().iloc[-2520:]
    lp = np.log(close.iloc[-2520:])
    out: List[Dict] = []
    jb = stats.jarque_bera(x)
    out.append({"test": "Jarque-Bera (normality of returns)", "stat": r(jb.statistic, 1), "p": r(jb.pvalue, 4),
                "verdict": "Not normal — fat tails" if jb.pvalue < 0.05 else "Consistent with normal",
                "meaning": ("Big moves happen far more often than a bell curve predicts — never size by standard deviation alone."
                            if jb.pvalue < 0.05 else "Returns look bell-shaped; textbook risk formulas are reasonable.")})
    try:
        from statsmodels.stats.diagnostic import acorr_ljungbox
        from statsmodels.tsa.stattools import adfuller, kpss
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            a_p = adfuller(lp.to_numpy(), maxlag=10, autolag=None)
            a_r = adfuller(x.to_numpy(), maxlag=10, autolag=None)
            k_p = kpss(lp.to_numpy(), regression="c", nlags="auto")
            k_r = kpss(x.to_numpy(), regression="c", nlags="auto")
        out.append({"test": "ADF on log price (unit root)", "stat": r(a_p[0], 2), "p": r(a_p[1], 4),
                    "verdict": "Random-walk price (unit root)" if a_p[1] > 0.05 else "Price mean-reverts",
                    "meaning": ("Price has no fixed 'fair level' to snap back to — trade trends and returns, not price levels."
                                if a_p[1] > 0.05 else "Price tends to revert to a level — range/mean-reversion trading is supported.")})
        out.append({"test": "ADF on daily returns", "stat": r(a_r[0], 2), "p": r(a_r[1], 4),
                    "verdict": "Stationary" if a_r[1] < 0.05 else "Non-stationary",
                    "meaning": "Returns are stable enough for statistics and models to be meaningful." if a_r[1] < 0.05
                    else "Even returns drift — treat all model outputs with extra caution."})
        out.append({"test": "KPSS on log price (stationarity)", "stat": r(k_p[0], 3), "p": r(k_p[1], 4),
                    "verdict": "Non-stationary (trending)" if k_p[1] < 0.05 else "Level-stationary",
                    "meaning": "Confirms ADF from the other side: the price wanders — don't fade a trend just because it looks 'too high'."
                    if k_p[1] < 0.05 else "Price oscillates around a stable level."})
        out.append({"test": "KPSS on daily returns", "stat": r(k_r[0], 3), "p": r(k_r[1], 4),
                    "verdict": "Stationary" if k_r[1] >= 0.05 else "Non-stationary",
                    "meaning": "Return behaviour is stable over time." if k_r[1] >= 0.05
                    else "Return behaviour shifts over time — prefer recent data and rolling estimates."})
        lb = acorr_ljungbox(x.to_numpy(), lags=[10])
        lb2 = acorr_ljungbox((x.to_numpy() - x.mean()) ** 2, lags=[10])
        p1, p2 = float(lb["lb_pvalue"].iloc[0]), float(lb2["lb_pvalue"].iloc[0])
        out.append({"test": "Ljung-Box (10 lags) on returns", "stat": r(lb["lb_stat"].iloc[0], 1), "p": r(p1, 4),
                    "verdict": "Autocorrelated" if p1 < 0.05 else "No autocorrelation",
                    "meaning": "Yesterday's move carries information about today — short-term timing rules can work."
                    if p1 < 0.05 else "Past daily moves don't predict the next one — short-term timing is mostly noise."})
        out.append({"test": "Ljung-Box on squared returns (ARCH effect)", "stat": r(lb2["lb_stat"].iloc[0], 1), "p": r(p2, 4),
                    "verdict": "Volatility clusters" if p2 < 0.05 else "No clustering",
                    "meaning": "Wild days follow wild days — after a shock, expect more; GARCH forecasts are informative."
                    if p2 < 0.05 else "Volatility doesn't cluster much — a shock today says little about tomorrow."})
    except Exception as e:  # statsmodels missing
        logger.warning(f"statsmodels tests unavailable: {e}")
    nonnorm = out[0]["p"] is not None and out[0]["p"] < 0.05
    rw = any(t["test"].startswith("ADF on log") and (t["p"] or 0) > 0.05 for t in out)
    cl = any(t["test"].startswith("Ljung-Box on squared") and (t["p"] or 1) < 0.05 for t in out)
    return {
        "tests": out,
        "insight": insight(
            "Textbook statistical checks (OpenBB 'quantitative' menu) on the last ~10 years: normality, unit root, stationarity and autocorrelation.",
            ("Returns are fat-tailed. " if nonnorm else "Returns look normal. ")
            + ("Price behaves like a random walk. " if rw else "Price shows mean reversion. ")
            + ("Volatility clusters." if cl else "Volatility does not cluster much."),
            "Use fat-tail-aware risk (Cornish-Fisher / historical VaR), trade returns not price levels, and "
            + ("scale exposure down right after big shocks." if cl else "keep sizing steady."),
        ),
    }


# ── rolling beta ─────────────────────────────────────────────────────────────

def _beta(ret: pd.Series, bench: Optional[pd.Series], bench_sym: str) -> Optional[Dict]:
    if bench is None or len(bench) < 300:
        return None
    br = bench.pct_change()
    df = pd.DataFrame({"a": ret, "b": br}).dropna()
    df = df[df.index >= df.index.max() - pd.Timedelta(days=6 * 365)]
    if len(df) < 300:
        return None
    cov = df["a"].rolling(252).cov(df["b"])
    var = df["b"].rolling(252).var()
    beta = cov / var
    corr = df["a"].rolling(252).corr(df["b"])
    tail = df.index >= df.index.max() - pd.Timedelta(days=5 * 365)
    ds = downsample(int(tail.sum()), 260)
    bt, ct = beta[tail].iloc[ds], corr[tail].iloc[ds]
    y = df.iloc[-252:]
    b_now = float(beta.iloc[-1]); c_now = float(corr.iloc[-1])
    alpha = float((y["a"].mean() - b_now * y["b"].mean()) * ANN * 100)
    up = y[y["b"] > 0]; dn = y[y["b"] < 0]
    upc = float(up["a"].mean() / up["b"].mean() * 100) if len(up) > 20 else None
    dnc = float(dn["a"].mean() / dn["b"].mean() * 100) if len(dn) > 20 else None
    nm = BENCH_NAMES.get(bench_sym, bench_sym)
    return {
        "benchmark": bench_sym, "benchmark_name": nm,
        "beta_now": r(b_now, 2), "corr_now": r(c_now, 2), "alpha_ann_pct": r(alpha, 1),
        "up_capture": r(upc, 0), "down_capture": r(dnc, 0),
        "series": {"dates": [str(i.date()) for i in bt.index], "beta": [r(v, 2) for v in bt], "corr": [r(v, 2) for v in ct]},
        "insight": insight(
            f"Rolling 1-year beta and correlation of daily returns vs {nm}, plus 1-year CAPM alpha and up/down capture.",
            f"Beta {b_now:.2f}: a 1% move in {nm} has meant ~{b_now:.2f}% here (correlation {c_now:.2f}). "
            + (f"It captured {upc:.0f}% of up-days and {dnc:.0f}% of down-days; " if upc is not None and dnc is not None else "")
            + f"alpha over the last year {alpha:+.1f}%/yr.",
            (f"Correlation is so low ({c_now:.2f}) that beta is not meaningful — this asset moves independently of {nm}, "
             "which makes it a genuine diversifier but means index hedges will NOT protect it."
             if abs(c_now) < 0.2 else
             "High beta — this amplifies the market; hold less of it than a plain index fund, or hedge with index puts."
             if b_now > 1.2 else
             "Low beta — a defensive holding that softens market falls; useful ballast in a portfolio."
             if b_now < 0.6 else
             "Market-like beta — moves with the index; diversification needs genuinely different assets.")
            + (" Asymmetric capture (more upside than downside) is a quality sign." if upc and dnc and upc > dnc + 10 else ""),
        ),
    }


# ── drawdown table (ffn) ─────────────────────────────────────────────────────

def _drawdowns(close: pd.Series, top: int = 5) -> Dict:
    peak = close.cummax()
    dd = close / peak - 1
    under = dd < 0
    grp = (under != under.shift()).cumsum()
    rows = []
    for _, seg in dd[under].groupby(grp[under]):
        trough_d = seg.idxmin()
        start = close.index[max(0, close.index.get_loc(seg.index[0]) - 1)]
        end_loc = close.index.get_loc(seg.index[-1]) + 1
        recovered = end_loc < len(close)
        rec_d = close.index[end_loc] if recovered else None
        rows.append({
            "peak": str(start.date()), "trough": str(trough_d.date()),
            "recovery": str(rec_d.date()) if rec_d is not None else None,
            "depth_pct": r(seg.min() * 100, 1),
            "days_to_trough": int(np.busday_count(start.date(), trough_d.date())),
            "days_to_recover": int(np.busday_count(trough_d.date(), rec_d.date())) if rec_d is not None else None,
            "total_days": int(np.busday_count(start.date(), (rec_d or close.index[-1]).date())),
        })
    rows.sort(key=lambda x: x["depth_pct"])
    t = rows[:top]
    cur = float(dd.iloc[-1] * 100)
    if not t:
        return {"rows": [], "current_pct": r(cur, 1), "insight": insight("No drawdowns found.", "", "")}
    w = t[0]
    med_rec = np.median([x["days_to_recover"] for x in t if x["days_to_recover"]]) if any(x["days_to_recover"] for x in t) else None
    return {
        "rows": t, "current_pct": r(cur, 1),
        "insight": insight(
            "The five deepest peak-to-trough falls in the full history, how long they took to bottom and to recover (ffn drawdown table).",
            f"Worst: {w['depth_pct']}% from {w['peak']} to {w['trough']}, "
            + (f"recovered after {w['days_to_recover']} trading days." if w["days_to_recover"] else "still not recovered.")
            + (f" The big ones typically took ~{med_rec/252:.1f} years to heal." if med_rec else "")
            + f" Today it is {cur:.1f}% below its peak.",
            "Before buying, ask: could I hold through a repeat of the worst row without selling? If not, size down or diversify — "
            "drawdowns like these are normal for this asset, not exceptions.",
        ),
    }


def _ord(x: float) -> str:
    n = int(round(x))
    suf = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


# ── volatility cone ─────────────────────────────────────────────────────────

def _vol_cone(ret: pd.Series) -> Dict:
    x = ret.dropna().iloc[-2520:]
    rows = []
    for w in (10, 21, 63, 126, 252):
        rv = (x.rolling(w).std() * np.sqrt(ANN) * 100).dropna()
        if len(rv) < 50:
            continue
        rows.append({"window": w, "min": r(rv.min(), 1), "p25": r(rv.quantile(.25), 1), "median": r(rv.median(), 1),
                     "p75": r(rv.quantile(.75), 1), "max": r(rv.max(), 1), "now": r(rv.iloc[-1], 1),
                     "pctile": r((rv < rv.iloc[-1]).mean() * 100, 0)})
    m = next((x for x in rows if x["window"] == 21), rows[0] if rows else None)
    return {
        "rows": rows,
        "insight": insight(
            "Volatility cone (OpenBB/options desk staple): range of realised vol for each look-back window over 10 years, with today's reading.",
            f"1-month realised vol {m['now']}% sits at the {_ord(m['pctile'])} percentile of its 10-year range ({m['min']}–{m['max']}%)." if m else "",
            ("Near the top of the cone — implied vol is likely rich; selling premium has the statistical edge."
             if m and m["pctile"] > 80 else
             "Near the bottom of the cone — options are likely cheap; buying protection or straddles has the edge."
             if m and m["pctile"] < 20 else
             "Mid-cone — no strong volatility edge; choose option strategies on directional view instead."),
        ),
    }


def build_regime(df: pd.DataFrame, symbol: str, bench: Optional[pd.Series] = None, bench_sym: str = "^GSPC") -> Dict:
    d = naive(df)
    if len(d) < 300:
        return {"success": False, "error": "need at least ~15 months of daily history"}
    close = d["Close"]
    ret = close.pct_change().dropna()
    b = naive(pd.DataFrame({"Close": bench}))["Close"] if bench is not None and len(bench) else None
    out = {"success": True, "symbol": symbol, "start": str(d.index[0].date())}
    blocks = {
        "rolling": lambda: _rolling(ret),
        "garch": lambda: fit_garch(ret),
        "hurst": lambda: _hurst(close),
        "regime": lambda: _regime(close, ret),
        "mc_cone": lambda: _mc_cone(close, ret),
        "var": lambda: _var_table(ret),
        "tests": lambda: _tests(close, ret),
        "beta": lambda: _beta(ret, b, bench_sym),
        "drawdowns": lambda: _drawdowns(close),
        "vol_cone": lambda: _vol_cone(ret),
    }
    for k, fn in blocks.items():
        try:
            out[k] = fn()
        except Exception as e:
            logger.warning(f"regime block {k} failed for {symbol}: {e}")
            out[k] = None
    return clean(out)
