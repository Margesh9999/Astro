"""
Quant Desk round-3 extensions — richer indicators, statistical memory,
cross-asset correlations, Monte-Carlo fan forecast and a setup-analog
prediction engine. Every block ships a plain-English actionable
interpretation, matching the house style of quant_analytics.py.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ── interpretation helpers ───────────────────────────────────────────────────

def _interpret_macd(hist_now: float, hist_prev: float) -> str:
    rising = hist_now > hist_prev
    if hist_now > 0 and rising:
        return ("MACD is above its signal line and the gap is widening — fresh buying pressure. "
                "Actionable: trend-following longs have the edge; hold winners with a trailing stop rather than fixed targets.")
    if hist_now > 0 and not rising:
        return ("MACD is positive but fading — the up-move is losing steam. "
                "Actionable: tighten stops on longs, take partial profits, and wait for a re-acceleration before adding.")
    if hist_now <= 0 and rising:
        return ("MACD is below its signal line but turning up — an early repair signal. "
                "Actionable: build a small watchlist position only on a confirmed cross above the signal line.")
    return ("MACD is negative and still falling — sellers remain in control. "
            "Actionable: avoid catching the knife; cash or hedged income is better until momentum resets.")


def _interpret_bollinger(upper: float, lower: float, pct_b: float) -> str:
    if pct_b >= 1:
        return (f"Price closed above the upper Bollinger band ({upper:.2f}) — momentum is stretched. "
                "Actionable: expect a breather; avoid chase-buys and sell covered calls into strength.")
    if pct_b <= 0:
        return (f"Price closed below the lower band ({lower:.2f}) — panic territory. "
                "Actionable: such closes statistically mean-revert within days; scale in small with hard stops.")
    if pct_b >= 0.8:
        return (f"Price sits in the top fifth of its bands (%B {pct_b:.2f}) — strong but not extreme. "
                "Actionable: longs stay on; trail stops up to the 20-day mid-band.")
    if pct_b <= 0.2:
        return (f"Price sits in the bottom fifth of its bands (%B {pct_b:.2f}) — weak but not broken. "
                "Actionable: wait for %B to reclaim 0.5 before committing fresh capital.")
    return (f"Price is mid-band (%B {pct_b:.2f}) — no band edge to trade against. "
            "Actionable: let the breakout come to you; band-mid ranges favour patient entries.")


def _interpret_stochastic(k: float, d: float) -> str:
    if k >= 80 and k > d:
        return (f"Stochastic %K {k:.0f} is overbought and above %D {d:.0f}. "
                "Actionable: momentum is hot — protect gains; fresh longs want a pullback toward %K 50.")
    if k <= 20 and k < d:
        return (f"Stochastic %K {k:.0f} is oversold and below %D {d:.0f}. "
                "Actionable: bounces from here are tradable; a %K cross back above %D is the buy trigger.")
    if k > d:
        return (f"Stochastic %K {k:.0f} above %D {d:.0f} — short-term momentum favours buyers. "
                "Actionable: ride existing longs and add on dips while the cross holds.")
    return (f"Stochastic %K {k:.0f} below %D {d:.0f} — short-term momentum favours sellers. "
            "Actionable: avoid new longs until %K turns back above %D.")


def _interpret_atr(atr_pct: float) -> str:
    if atr_pct >= 3:
        return (f"Average True Range is {atr_pct:.1f}% of price — a wide-swing environment. "
                "Actionable: halve position size so the same money-risk fits inside the bigger daily range.")
    if atr_pct <= 1:
        return (f"Average True Range is a quiet {atr_pct:.1f}% of price. "
                "Actionable: premium-selling and range strategies pay best when daily movement is this small.")
    return (f"Average True Range is {atr_pct:.1f}% of price — normal movement. "
            "Actionable: standard sizing applies; swing stops placed roughly 2× ATR away survive the noise.")


def _interpret_obv(obv_up20: bool, perf_1m: float) -> str:
    if obv_up20 and perf_1m > 0:
        return ("Volume flow confirms the price rise — accumulation. "
                "Actionable: the trend has fuel; hold longs while OBV keeps printing higher lows.")
    if not obv_up20 and perf_1m > 0:
        return ("Price is rising but On-Balance Volume is falling — a bearish divergence: the rally runs on thinning demand. "
                "Actionable: reduce long size and do not add until volume confirms.")
    if obv_up20 and perf_1m <= 0:
        return ("Price is flat-to-down yet OBV is rising — quiet accumulation, often a base building. "
                "Actionable: keep a buying plan ready for the breakout candle.")
    return ("Both price and volume are draining — distribution. "
            "Actionable: stand aside; re-entry waits for OBV to turn up alongside price.")


def _interpret_memory(hurst: float) -> str:
    if hurst > 0.55:
        return (f"Hurst exponent {hurst:.2f} (> 0.55) — returns show persistent, trending memory. "
                "Actionable: momentum and breakout tactics historically work best here; fade-the-move tactics lose.")
    if hurst < 0.45:
        return (f"Hurst exponent {hurst:.2f} (< 0.45) — a strong mean-reversion signature. "
                "Actionable: buy dips and sell rips around the 20-day band rather than chasing breakouts.")
    return (f"Hurst exponent {hurst:.2f} ≈ 0.5 — near random walk; yesterday's direction says little about tomorrow. "
            "Actionable: favour range and options-income tactics over outright directional bets.")


# ── series builders ──────────────────────────────────────────────────────────

def _naive_index(idx) -> pd.DatetimeIndex:
    try:
        if getattr(idx, "tz", None) is not None:
            return idx.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    return pd.DatetimeIndex(idx)


def _macd_series(close: pd.Series):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal


def _bollinger_series(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    upper = mid + k * sd
    lower = mid - k * sd
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    return upper, mid, lower, pct_b


def _stochastic_series(d: pd.DataFrame, n: int = 14):
    ll = d["Low"].rolling(n).min()
    hh = d["High"].rolling(n).max()
    rng = (hh - ll).replace(0, np.nan)
    raw = (d["Close"] - ll) / rng * 100.0
    k = raw.rolling(3).mean()
    dl = k.rolling(3).mean()
    return k, dl


def _atr_pct_series(d: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = d["Close"].shift(1)
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - prev).abs(), (d["Low"] - prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    return atr / d["Close"] * 100.0


def _obv_series(d: pd.DataFrame) -> pd.Series:
    direction = np.sign(d["Close"].diff().fillna(0.0))
    obv = (direction * d["Volume"].astype(float)).cumsum()
    return obv - obv.iloc[0]


def _rolling_sharpe_series(ret: pd.Series, n: int = 63) -> pd.Series:
    mu = ret.rolling(n).mean()
    sd = ret.rolling(n).std().replace(0, np.nan)
    return (mu / sd) * np.sqrt(252)


def _hurst_exponent(close: pd.Series) -> float:
    """Rescaled-range Hurst exponent on daily log returns (0.5 = random walk)."""
    lp = np.log(close.values.astype(float))
    r = np.diff(lp)
    n = len(r)
    if n < 100:
        return 0.5
    sizes = [s for s in (8, 16, 32, 64, 128, 256, 512, 1024) if 16 <= s <= n // 4]
    if len(sizes) < 3:
        return 0.5
    xs, ys = [], []
    for s in sizes:
        m = n // s
        rs_vals = []
        for i in range(m):
            seg = r[i * s:(i + 1) * s]
            dev = seg - seg.mean()
            z = np.cumsum(dev)
            span = z.max() - z.min()
            sd = dev.std(ddof=0)
            if sd > 1e-12:
                rs_vals.append(span / sd)
        if rs_vals:
            xs.append(np.log(s))
            ys.append(np.log(float(np.mean(rs_vals))))
    if len(xs) < 3:
        return 0.5
    return float(np.clip(np.polyfit(xs, ys, 1)[0], 0.0, 1.0))


def _acf_values(ret: pd.Series, max_lag: int = 10) -> List[float]:
    r = ret.dropna().values
    out = []
    for lag in range(1, max_lag + 1):
        a, b = r[:-lag], r[lag:]
        if len(a) > 30 and a.std() > 1e-12 and b.std() > 1e-12:
            out.append(round(float(np.corrcoef(a, b)[0, 1]), 3))
        else:
            out.append(0.0)
    return out


def _return_histogram(ret: pd.Series, bins: int = 33, clip_sigma: float = 4.0) -> List[Dict]:
    r = ret.dropna()
    sd = float(r.std()) or 0.01
    clipped = r.clip(-clip_sigma * sd, clip_sigma * sd)
    counts, edges = np.histogram(clipped.values, bins=bins)
    centers = ((edges[:-1] + edges[1:]) / 2.0) / sd
    return [{"center": round(float(c), 2), "count": int(n)} for c, n in zip(centers, counts)]


def _correlation_pack(close: pd.Series, benchmark_closes: Optional[Dict[str, pd.Series]],
                      benchmark_names: Optional[Dict[str, str]]) -> Optional[Dict]:
    """Past-year daily-return correlations of `close` vs benchmark assets."""
    series = {"@this": close}
    for sym, s in (benchmark_closes or {}).items():
        series[sym] = s
    panel = pd.DataFrame({k: pd.Series(v.values, index=_naive_index(v.index)) for k, v in series.items()})
    panel = panel.sort_index().tail(252).dropna(axis=0, how="all")
    if len(panel) < 60:
        return None
    rets = panel.pct_change().dropna(how="all")
    if len(rets) < 50:
        return None
    corr = rets.corr(min_periods=40)
    pairs = []
    for sym in (benchmark_closes or {}):
        if sym in corr.index and not np.isnan(corr.loc["@this", sym]):
            pairs.append({"symbol": sym, "name": (benchmark_names or {}).get(sym, sym),
                          "corr": round(float(corr.loc["@this", sym]), 2)})
    if not pairs:
        return None
    pairs.sort(key=lambda p: -p["corr"])
    mat_syms = ["@this"] + [p["symbol"] for p in pairs]
    matrix = [[round(float(corr.loc[a, b]), 2) if not np.isnan(corr.loc[a, b]) else None
               for b in mat_syms] for a in mat_syms]
    best = max(pairs, key=lambda p: p["corr"])
    div = min(pairs, key=lambda p: abs(p["corr"]))
    if best["corr"] >= 0.6:
        ally = f"{best['name']} (r={best['corr']:+.2f}) moves almost in lockstep — it is your read-across and best hedge"
    elif best["corr"] >= 0.3:
        ally = f"{best['name']} (r={best['corr']:+.2f}) is the closest co-mover"
    else:
        ally = f"no benchmark is strongly coupled right now (closest {best['name']} at r={best['corr']:+.2f})"
    interp = (f"Past-year daily co-movement: {ally}; {div['name']} (r={div['corr']:+.2f}) is the best diversifier. "
              "Actionable: hedges and pair trades belong on the high-|r| names; treat the low-r assets as portfolio ballast.")
    return {"pairs": pairs,
            "matrix": {"symbols": mat_syms, "values": matrix},
            "observation_days": int(len(rets)),
            "interpretation": interp}


def _mc_forecast(close: pd.Series, ret: pd.Series, days: int = 21,
                 n_paths: int = 600, block: int = 5, seed: int = 42) -> Optional[Dict]:
    """Block-bootstrap Monte-Carlo fan chart from the last year of daily returns."""
    r = ret.dropna().tail(252).values
    if len(r) < 60:
        return None
    rng = np.random.default_rng(seed)
    n = len(r)
    starts = rng.integers(0, n - block, size=(n_paths, days // block + 1))
    paths = np.empty((n_paths, days))
    for i in range(n_paths):
        seq = np.concatenate([r[starts[i, j]:starts[i, j] + block] for j in range(starts.shape[1])])[:days]
        paths[i] = seq
    sim = float(close.iloc[-1]) * np.cumprod(1.0 + paths, axis=1)
    qs = np.percentile(sim, [5, 25, 50, 75, 95], axis=1)
    last = float(close.iloc[-1])
    idx = _naive_index(close.index)
    future = [str(x.date()) for x in pd.bdate_range(pd.Timestamp(idx[-1]) + pd.Timedelta(days=1), periods=days)]
    return {
        "dates": future,
        "p5": [round(float(v), 2) for v in qs[0]],
        "p25": [round(float(v), 2) for v in qs[1]],
        "p50": [round(float(v), 2) for v in qs[2]],
        "p75": [round(float(v), 2) for v in qs[3]],
        "p95": [round(float(v), 2) for v in qs[4]],
        "last": round(last, 2),
        "prob_up_1w": round(float((sim[:, 4] > last).mean()) * 100, 1),
        "prob_up_1m": round(float((sim[:, -1] > last).mean()) * 100, 1),
        "expected_1m_pct": round(float(np.mean(sim[:, -1]) / last - 1) * 100, 2),
        "range_low_1w": round(float(qs[0, 4]), 2), "range_high_1w": round(float(qs[4, 4]), 2),
        "range_low_1m": round(float(qs[0, -1]), 2), "range_high_1m": round(float(qs[4, -1]), 2),
        "paths": int(n_paths), "days": days,
        "method": ("block bootstrap: 600 alternative 21-day paths resampled from the last 252 daily returns "
                   "(5-day blocks preserve volatility clustering)"),
    }


def _analog_evidence(close: pd.Series, hist: pd.Series, rsi_s: pd.Series,
                     sma50: pd.Series, sma200: pd.Series, vol21: pd.Series, vol_med: float) -> Optional[Dict]:
    """Setup-analog engine: fingerprint today's regime, replay the full history."""
    flags = {
        "above50": (close > sma50).fillna(False),
        "above200": (close > sma200).fillna(False),
        "macd_pos": (hist > 0).fillna(False),
        "rsi_pos": (rsi_s > 50).fillna(False),
        "vol_high": (vol21 > vol_med).fillna(False),
    }
    keys = sorted(flags.keys())
    code_series = pd.Series(0, index=close.index)
    for i, k in enumerate(keys):
        code_series = code_series + flags[k].astype(int) * (2 ** i)
    today_code = int(code_series.iloc[-1])
    fwd = {h: (close.shift(-n) / close - 1.0) for h, n in (("5d", 5), ("10d", 10), ("21d", 21))}
    mask = code_series == today_code
    ev: Dict = {"count": int(mask.sum()), "code": today_code}
    for h, s in fwd.items():
        m = mask & s.notna()
        if int(m.sum()) < 5:
            ev[h] = None
            continue
        vals = s[m]
        ev[h] = {"count": int(m.sum()),
                 "hit_rate": round(float((vals > 0).mean()) * 100, 1),
                 "mean_pct": round(float(vals.mean()) * 100, 2),
                 "median_pct": round(float(vals.median()) * 100, 2),
                 "best_pct": round(float(vals.max()) * 100, 1),
                 "worst_pct": round(float(vals.min()) * 100, 1)}
    labels = {"above50": "price above 50-day", "above200": "price above 200-day",
              "macd_pos": "MACD positive", "rsi_pos": "RSI above 50", "vol_high": "volatility elevated"}
    today_flags = {k: bool(flags[k].iloc[-1]) for k in keys}
    ev["description"] = " · ".join(f"{labels[k]} ({'✓' if today_flags[k] else '✗'})" for k in keys)
    e21 = ev.get("21d")
    if e21:
        verdict = ("the odds tilt positive — size longs accordingly but respect the worst-case number"
                   if e21["mean_pct"] > 0 and e21["hit_rate"] >= 55 else
                   "the edge is thin or negative — keep positions small and prefer income strategies"
                   if e21["hit_rate"] < 50 else
                   "evidence is mixed — let price confirmation, not hope, trigger entries")
        ev["interpretation"] = (
            f"This exact behavioural fingerprint — {ev['description']} — occurred {ev['count']} times in the full history. "
            f"21 days later the market was higher {e21['hit_rate']}% of the time with an average move of {e21['mean_pct']:+.1f}% "
            f"(median {e21['median_pct']:+.1f}%, best {e21['best_pct']:+.1f}%, worst {e21['worst_pct']:+.1f}%). "
            f"Actionable: {verdict}.")
    else:
        ev["interpretation"] = (f"This fingerprint — {ev['description']} — is rare with no reliable forward sample. "
                                "Actionable: treat it as uncharted territory and size positions conservatively.")
    return ev


def _synthesise_signals(price: float, s50: float, s200: float, hist: pd.Series,
                        rsi_now: float, k_now: float, d_now: float, vol_ratio: float,
                        obv_up20: bool, perf_1m: float, hurst: float, month_avg: float,
                        mc: Optional[Dict]) -> Dict:
    """Weighted rule synthesis across pillars → composite score + verdict."""
    pillars: List[Dict] = []

    if price > s50 > s200:
        pillars.append({"name": "Trend", "reading": f"Price above both 50- and 200-day averages ({s50:.0f} / {s200:.0f})", "stance": "bullish", "weight": 2.0})
    elif price < s50 < s200:
        pillars.append({"name": "Trend", "reading": f"Price below both key averages ({s50:.0f} / {s200:.0f})", "stance": "bearish", "weight": -2.0})
    elif price > s200:
        pillars.append({"name": "Trend", "reading": "Above the 200-day but under the 50-day — repairing", "stance": "neutral", "weight": 0.5})
    else:
        pillars.append({"name": "Trend", "reading": "Under the 200-day average — primary trend damaged", "stance": "bearish", "weight": -1.0})

    hist_now = float(hist.iloc[-1]); hist_prev = float(hist.iloc[-2])
    if hist_now > 0 and hist_now > hist_prev:
        pillars.append({"name": "MACD", "reading": f"Positive and widening ({hist_now:.2f})", "stance": "bullish", "weight": 1.5})
    elif hist_now > 0:
        pillars.append({"name": "MACD", "reading": f"Positive but fading ({hist_now:.2f})", "stance": "neutral", "weight": 0.5})
    elif hist_now > hist_prev:
        pillars.append({"name": "MACD", "reading": f"Negative but turning up ({hist_now:.2f})", "stance": "neutral", "weight": -0.5})
    else:
        pillars.append({"name": "MACD", "reading": f"Negative and falling ({hist_now:.2f})", "stance": "bearish", "weight": -1.5})

    if rsi_now >= 70:
        pillars.append({"name": "RSI", "reading": f"{rsi_now:.0f} — overbought", "stance": "neutral", "weight": 0.5})
    elif rsi_now <= 30:
        pillars.append({"name": "RSI", "reading": f"{rsi_now:.0f} — oversold", "stance": "neutral", "weight": -0.5})
    else:
        pillars.append({"name": "RSI", "reading": f"{rsi_now:.0f} — {'bull zone' if rsi_now > 50 else 'bear zone'}",
                        "stance": "bullish" if rsi_now > 50 else "bearish", "weight": 1.0 if rsi_now > 50 else -1.0})

    if k_now > d_now and k_now < 80:
        pillars.append({"name": "Stochastic", "reading": f"%K {k_now:.0f} above %D {d_now:.0f}", "stance": "bullish", "weight": 1.0})
    elif k_now > d_now:
        pillars.append({"name": "Stochastic", "reading": f"%K {k_now:.0f} hot and rising", "stance": "neutral", "weight": 0.3})
    elif k_now < d_now and k_now > 20:
        pillars.append({"name": "Stochastic", "reading": f"%K {k_now:.0f} below %D {d_now:.0f}", "stance": "bearish", "weight": -1.0})
    else:
        pillars.append({"name": "Stochastic", "reading": f"%K {k_now:.0f} washed out", "stance": "neutral", "weight": -0.3})

    if vol_ratio > 1.4:
        pillars.append({"name": "Volatility", "reading": f"{vol_ratio:.1f}× typical — stress regime", "stance": "bearish", "weight": -1.0})
    elif vol_ratio < 0.75:
        pillars.append({"name": "Volatility", "reading": f"{vol_ratio:.1f}× typical — calm regime", "stance": "bullish", "weight": 0.5})
    else:
        pillars.append({"name": "Volatility", "reading": f"{vol_ratio:.1f}× typical — normal", "stance": "neutral", "weight": 0.0})

    if obv_up20 and perf_1m > 0:
        pillars.append({"name": "Volume", "reading": "OBV rising with price — confirmed", "stance": "bullish", "weight": 1.0})
    elif not obv_up20 and perf_1m > 0:
        pillars.append({"name": "Volume", "reading": "OBV falling vs price — divergence", "stance": "bearish", "weight": -1.0})
    elif obv_up20:
        pillars.append({"name": "Volume", "reading": "OBV rising into weakness — accumulation", "stance": "bullish", "weight": 0.5})
    else:
        pillars.append({"name": "Volume", "reading": "OBV falling — distribution", "stance": "bearish", "weight": -0.5})

    if hurst > 0.55:
        pillars.append({"name": "Memory (Hurst)", "reading": f"{hurst:.2f} — trending regime",
                        "stance": "bullish" if perf_1m > 0 else "bearish", "weight": 0.5 if perf_1m > 0 else -0.5})
    elif hurst < 0.45:
        pillars.append({"name": "Memory (Hurst)", "reading": f"{hurst:.2f} — mean-reverting regime",
                        "stance": "bullish" if perf_1m < 0 else "bearish", "weight": 0.5 if perf_1m < 0 else -0.5})
    else:
        pillars.append({"name": "Memory (Hurst)", "reading": f"{hurst:.2f} — no memory edge", "stance": "neutral", "weight": 0.0})

    if month_avg >= 1.0:
        pillars.append({"name": "Seasonality", "reading": f"This month averages {month_avg:+.1f}%", "stance": "bullish", "weight": 0.5})
    elif month_avg <= -1.0:
        pillars.append({"name": "Seasonality", "reading": f"This month averages {month_avg:+.1f}%", "stance": "bearish", "weight": -0.5})
    else:
        pillars.append({"name": "Seasonality", "reading": f"This month averages {month_avg:+.1f}%", "stance": "neutral", "weight": 0.0})

    raw = sum(p["weight"] for p in pillars)
    score = int(round(max(-100.0, min(100.0, raw / 8.0 * 100.0))))
    label = ("Strong Bullish" if score >= 40 else "Bullish" if score >= 15 else
             "Neutral" if score > -15 else "Bearish" if score > -40 else "Strong Bearish")
    n_bull = sum(1 for p in pillars if p["stance"] == "bullish")
    n_bear = sum(1 for p in pillars if p["stance"] == "bearish")
    headline = (f"{label} — composite {score:+d}/100 from {n_bull} bullish and {n_bear} bearish pillars. "
                + (f"Block-bootstrap odds of a higher close in a month: {mc['prob_up_1m']}%."
                   if mc else "Not enough history for a bootstrap forecast."))
    return {"score": score, "label": label, "pillars": pillars, "headline": headline,
            "n_bull": n_bull, "n_bear": n_bear}


# ── main entry ───────────────────────────────────────────────────────────────

def extend_pack(d: pd.DataFrame, close: pd.Series, ret: pd.Series,
                ctx: Dict, benchmark_closes: Optional[Dict[str, pd.Series]] = None,
                benchmark_names: Optional[Dict[str, str]] = None) -> Dict:
    """
    Build the round-3 analytics blocks. `ctx` carries series already computed
    by quant_analytics.build_analytics to avoid duplicate work:
      rsi, sma50, sma200, vol21, vol_med (fraction), perf (dict), month_avg.
    Returns a dict to merge into the analytics pack (all values JSON-safe).
    """
    out: Dict = {}
    trim = d.index >= (d.index.max() - pd.Timedelta(days=730))
    dates = [str(i.date()) for i in d.index[trim]]
    # ctx["vol21"] is annualised PERCENT; ctx["vol_med"] is a FRACTION — align units
    vol21_frac = ctx["vol21"] / 100.0

    def _vals(s, nd=2):
        return [round(float(v), nd) if not np.isnan(v) else None for v in s[trim]]

    # MACD ────────────────────────────────────────────────────────────────────
    macd, signal, hist = _macd_series(close)
    hist_now = float(hist.iloc[-1]); hist_prev = float(hist.iloc[-2])
    out["macd"] = {
        "series": {"dates": dates, "macd": _vals(macd, 3), "signal": _vals(signal, 3), "hist": _vals(hist, 3)},
        "macd_now": round(float(macd.iloc[-1]), 3), "signal_now": round(float(signal.iloc[-1]), 3),
        "hist_now": round(hist_now, 3),
        "interpretation": _interpret_macd(hist_now, hist_prev),
    }

    # Bollinger ───────────────────────────────────────────────────────────────
    bb_u, bb_m, bb_l, pct_b = _bollinger_series(close)
    pb_now = float(pct_b.iloc[-1]) if not np.isnan(pct_b.iloc[-1]) else 0.5
    out["bollinger"] = {
        "series": {"dates": dates, "close": [round(float(v), 2) for v in close[trim]],
                   "upper": _vals(bb_u), "mid": _vals(bb_m), "lower": _vals(bb_l)},
        "upper_now": round(float(bb_u.iloc[-1]), 2), "lower_now": round(float(bb_l.iloc[-1]), 2),
        "pct_b": round(pb_now, 2),
        "interpretation": _interpret_bollinger(float(bb_u.iloc[-1]), float(bb_l.iloc[-1]), pb_now),
    }

    # Stochastic ──────────────────────────────────────────────────────────────
    k_s, d_s = _stochastic_series(d)
    k_now = float(k_s.iloc[-1]) if not np.isnan(k_s.iloc[-1]) else 50.0
    d_now = float(d_s.iloc[-1]) if not np.isnan(d_s.iloc[-1]) else 50.0
    out["stochastic"] = {
        "series": {"dates": dates, "k": _vals(k_s, 1), "d": _vals(d_s, 1)},
        "k_now": round(k_now, 1), "d_now": round(d_now, 1),
        "interpretation": _interpret_stochastic(k_now, d_now),
    }

    # ATR (% of price) ────────────────────────────────────────────────────────
    atr_pct = _atr_pct_series(d)
    atr_now = float(atr_pct.iloc[-1]) if not np.isnan(atr_pct.iloc[-1]) else 1.5
    out["atr"] = {
        "series": {"dates": dates, "atr_pct": _vals(atr_pct, 2)},
        "now_pct": round(atr_now, 2),
        "interpretation": _interpret_atr(atr_now),
    }

    # OBV ─────────────────────────────────────────────────────────────────────
    obv = _obv_series(d)
    obv_up20 = bool(obv.iloc[-1] > obv.iloc[-21]) if len(obv) > 21 else True
    out["obv"] = {
        "series": {"dates": dates, "obv": [int(round(float(v))) for v in obv[trim]]},
        "trend_20d": "rising" if obv_up20 else "falling",
        "interpretation": _interpret_obv(obv_up20, float(ctx.get("perf", {}).get("1m", 0.0))),
    }

    # Rolling Sharpe ──────────────────────────────────────────────────────────
    rs = _rolling_sharpe_series(ret)
    rs_now = float(rs.iloc[-1]) if not np.isnan(rs.iloc[-1]) else 0.0
    out["rolling_sharpe"] = {
        "series": {"dates": dates, "sharpe": _vals(rs, 2)},
        "now": round(rs_now, 2),
        "interpretation": (f"Rolling 63-day Sharpe is {rs_now:.2f} — "
                           + ("risk-adjusted momentum is strong; trend riders are being paid."
                              if rs_now > 1.0 else
                              "recent risk-adjusted returns are poor; be picky and demand confirmation."
                              if rs_now < 0 else
                              "middling risk-adjusted returns; normal selectivity applies.")
                           + " Actionable: combine with the trend filter — strong Sharpe + uptrend is the green-light zone."),
    }

    # Return distribution ─────────────────────────────────────────────────────
    r = ret.dropna()
    sd = float(r.std()) or 0.01
    var95 = float(np.percentile(r, 5)) * 100
    best_day = float(r.max()) * 100; worst_day = float(r.min()) * 100
    out["distribution"] = {
        "bins": _return_histogram(ret),
        "sigma_pct": round(sd * 100, 2),
        "var95_daily_pct": round(var95, 2),
        "best_day_pct": round(best_day, 2),
        "worst_day_pct": round(worst_day, 2),
        "interpretation": (f"Daily moves centre on ±{sd*100:.2f}% but the tails are fat: the worst single day was "
                           f"{worst_day:.1f}% and the best {best_day:.1f}%; 1-day 95% VaR is {abs(var95):.1f}%. "
                           "Actionable: never size a position as if the average day is the worst day — assume 3σ gaps happen."),
    }

    # Statistical memory ──────────────────────────────────────────────────────
    hurst = _hurst_exponent(close)
    acf = _acf_values(ret)
    regime = "trending" if hurst > 0.55 else "mean-reverting" if hurst < 0.45 else "random-walk"
    out["memory"] = {
        "acf": [{"lag": i + 1, "value": v} for i, v in enumerate(acf)],
        "acf1": acf[0] if acf else 0.0,
        "hurst": round(hurst, 2),
        "regime": regime,
        "interpretation": _interpret_memory(hurst),
    }

    # Correlations vs benchmarks ──────────────────────────────────────────────
    corr = _correlation_pack(close, benchmark_closes, benchmark_names)
    if corr:
        out["correlations"] = corr

    # Monte-Carlo fan forecast ────────────────────────────────────────────────
    mc = _mc_forecast(close, ret)
    syn = _synthesise_signals(
        price=float(close.iloc[-1]),
        s50=float(ctx["sma50"].iloc[-1]) if not np.isnan(ctx["sma50"].iloc[-1]) else float(close.iloc[-1]),
        s200=float(ctx["sma200"].iloc[-1]) if not np.isnan(ctx["sma200"].iloc[-1]) else float(close.iloc[-1]),
        hist=hist, rsi_now=float(ctx["rsi"].iloc[-1]) if not np.isnan(ctx["rsi"].iloc[-1]) else 50.0,
        k_now=k_now, d_now=d_now, vol_ratio=float(vol21_frac.iloc[-1]) / max(ctx["vol_med"], 1e-9),
        obv_up20=obv_up20, perf_1m=float(ctx.get("perf", {}).get("1m", 0.0)),
        hurst=hurst, month_avg=float(ctx.get("month_avg", 0.0)), mc=mc)

    # key levels + case builders
    w52 = close.tail(252)
    hi52 = float(w52.max()); lo52 = float(w52.min())
    s50v = float(ctx["sma50"].iloc[-1]) if not np.isnan(ctx["sma50"].iloc[-1]) else float(close.iloc[-1])
    s200v = float(ctx["sma200"].iloc[-1]) if not np.isnan(ctx["sma200"].iloc[-1]) else float(close.iloc[-1])
    s20v = float(close.rolling(20).mean().iloc[-1])
    levels = [{"level": "52-week high", "value": round(hi52, 2)},
              {"level": "SMA 20", "value": round(s20v, 2)},
              {"level": "SMA 50", "value": round(s50v, 2)},
              {"level": "SMA 200", "value": round(s200v, 2)},
              {"level": "52-week low", "value": round(lo52, 2)}]
    last_price = float(close.iloc[-1])
    stop_level = s50v if last_price > s50v else s200v
    invalidation = (f"A daily close below {stop_level:,.2f} ({'the 50-day' if last_price > s50v else 'the 200-day'} average) "
                    "invalidates the constructive case — cut or hedge there without negotiation.")

    analogs = _analog_evidence(close, hist, ctx["rsi"], ctx["sma50"], ctx["sma200"], vol21_frac, ctx["vol_med"])
    e21 = (analogs or {}).get("21d")
    bull_case = (f"If the pattern holds ({syn['label'].lower()} composite, {len([p for p in syn['pillars'] if p['stance']=='bullish'])} bullish pillars"
                 + (f", historical analog hit-rate {e21['hit_rate']}%" if e21 else "")
                 + f"), the path of least resistance is up toward {round(hi52,2):,.2f} (52-week high); "
                 f"a breakout there opens uncharted air. Scale in on quiet days and let winners run.")
    bear_case = (f"If the {len([p for p in syn['pillars'] if p['stance']=='bearish'])} bearish pillars take over"
                 + (f" (analog worst case {e21['worst_pct']:+.1f}% in 21 days)" if e21 else "")
                 + f", expect the {stop_level:,.2f} line to be tested first; losing it targets {round(lo52,2):,.2f} (52-week low). "
                 "Keep hedges or defined-risk structures on while price sits below the key averages.")

    fc = {
        "mc": mc,
        "signal": syn,
        "levels": levels,
        "invalidation": invalidation,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "analogs": analogs,
    }
    if mc:
        fc["horizons"] = [
            {"horizon": "1 Week", "bias": "up" if syn["score"] >= 15 else "down" if syn["score"] <= -15 else "flat",
             "range_low": mc["range_low_1w"], "range_high": mc["range_high_1w"],
             "note": f"{mc['prob_up_1w']}% bootstrap odds of a higher close; 90% of paths land between "
                     f"{mc['range_low_1w']:,.2f} and {mc['range_high_1w']:,.2f}."},
            {"horizon": "1 Month", "bias": "up" if syn["score"] >= 15 else "down" if syn["score"] <= -15 else "flat",
             "range_low": mc["range_low_1m"], "range_high": mc["range_high_1m"],
             "note": f"{mc['prob_up_1m']}% odds of finishing above {mc['last']:,.2f}; expected value "
                     f"{mc['expected_1m_pct']:+.1f}%. Ranges are modelled, not promised."},
        ]
    else:
        fc["horizons"] = [{"horizon": "1 Week / 1 Month", "bias": "n/a", "range_low": 0, "range_high": 0,
                           "note": "Not enough price history for a statistically meaningful bootstrap."}]
    fc["forecast_interpretation"] = (
        f"Behaviour synthesis: {syn['headline']} "
        + (f"The analog engine adds history's verdict: {analogs['interpretation'].split('Actionable: ')[-1]}" if analogs and analogs.get("interpretation") else "")
        + f" {invalidation}")
    out["forecast"] = fc
    return out
