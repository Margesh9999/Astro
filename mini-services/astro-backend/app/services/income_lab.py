"""v1.7 Income Strategy Lab: does an astro filter make weekly premium selling more consistent?

A rules-based back-test of the most common "consistent income" trade in India: selling a weekly
defined-risk option spread on the Nifty, every week, for 15+ years, then the same trade with
each astrological filter switched on.

Model (stated plainly, because it is a model):
  * Entry at the close of the first session of each week, exit at the close of the last.
  * Strikes by delta: short leg at ~0.20 delta (0.15 for the condor), long leg 1.5% further out.
  * Premiums priced with Black-Scholes from the volatility index (India VIX for the Nifty, VIX
    for the S&P 500) plus a simple skew; before the index existed, 20-day realised vol x 1.1.
    Real fills differ, so read results as indicative, not as a broker statement.
  * Costs of 0.02% of spot per spread (brokerage, taxes, slippage).
  * Position size is set by risk: the most the week can lose is a fixed share of capital (default
    5%). Margin is assumed to be pledged liquid funds, so the whole account keeps earning the
    liquid-fund rate.

Each filter is then compared with skipping the same number of *random* weeks (300 draws), so a
filter only counts as helping when it beats chance, not just because sitting out lowers risk.

Educational and illustrative only. Not financial advice.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import norm

logger = logging.getLogger(__name__)

RATE = 0.065          # risk-free / liquid-fund rate
COST = 0.0002         # per spread, fraction of spot
WIDTH = 0.015         # long leg distance beyond the short strike, fraction of spot
SKEW = {"put_short": 1.5, "put_long": 3.0, "call_short": -1.0, "call_long": -1.5}  # vol points vs ATM
VOL_INDEX = {"^NSEI": "^INDIAVIX", "^NSEBANK": "^INDIAVIX", "^GSPC": "^VIX", "SPY": "^VIX", "^NDX": "^VXN"}
VOL_MULT = {"^NSEBANK": 1.25}
N_RANDOM = 300

STRATEGIES = {
    "put_spread": "Bull put spread (sell ~0.20-delta put, buy 1.5% lower)",
    "call_spread": "Bear call spread (sell ~0.20-delta call, buy 1.5% higher)",
    "iron_condor": "Iron condor (sell ~0.15-delta put and call, wings 1.5% out)",
}
FILTERS = {
    "none": "Trade every week (no filter)",
    "skip_amavasya_purnima": "Skip weeks with Amavasya or Purnima on a trading day",
    "skip_eclipse": "Skip eclipse weeks",
    "skip_mercury_retro": "Skip weeks when Mercury is retrograde",
    "skip_outlook_down": "Skip weeks the sector outlook leans down (puts) / up (calls)",
    "skip_high_vol": "Control (not astrology): skip weeks when the vol index is in its top 20%",
}
SHORT = {
    "skip_amavasya_purnima": "Amavasya/Purnima",
    "skip_eclipse": "eclipse",
    "skip_mercury_retro": "Mercury retrograde",
    "skip_outlook_down": "sector outlook",
    "skip_high_vol": "high-volatility control",
}


def worst_phrase(pct: float) -> str:
    """Plain words for the worst week: a defined-risk spread can lose its whole margin plus costs."""
    return "the worst week lost the full max loss" if pct <= -99 else f"the worst week lost {abs(pct)}% of that margin"


def _bs(S: float, K: float, T: float, sig: float, call: bool) -> float:
    if T <= 0 or sig <= 0:
        return max(0.0, (S - K) if call else (K - S))
    d1 = (math.log(S / K) + (RATE + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    if call:
        return S * norm.cdf(d1) - K * math.exp(-RATE * T) * norm.cdf(d2)
    return K * math.exp(-RATE * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def _strike(S: float, T: float, sig: float, delta: float, call: bool) -> float:
    d1 = norm.ppf(delta) if call else -norm.ppf(delta)
    return S * math.exp(-d1 * sig * math.sqrt(T) + (RATE + 0.5 * sig * sig) * T)


def spread_trade(S: float, ST: float, T: float, iv: float, kind: str) -> Dict:
    """Price one weekly spread at entry and settle it at ST. Returns points P/L and margin."""
    def leg(call: bool, delta: float) -> Tuple[float, float, float, float]:
        sk = "call" if call else "put"
        s1 = max(iv + SKEW[f"{sk}_short"] / 100, 0.03)
        s2 = max(iv + SKEW[f"{sk}_long"] / 100, 0.03)
        k1 = _strike(S, T, s1, delta, call)
        k2 = k1 * (1 + WIDTH) if call else k1 * (1 - WIDTH)
        credit = _bs(S, k1, T, s1, call) - _bs(S, k2, T, s2, call)
        if call:
            loss = max(ST - k1, 0) - max(ST - k2, 0)
        else:
            loss = max(k1 - ST, 0) - max(k2 - ST, 0)
        return k1, k2, credit, loss

    if kind == "iron_condor":
        p = leg(False, 0.15)
        c = leg(True, 0.15)
        credit = p[2] + c[2]
        loss = p[3] + c[3]
        width = max(abs(p[0] - p[1]), abs(c[1] - c[0]))
        cost = 2 * COST * S
        legs = {"short_put": p[0], "long_put": p[1], "short_call": c[0], "long_call": c[1]}
    else:
        call = kind == "call_spread"
        k1, k2, credit, loss = leg(call, 0.20)
        width = abs(k2 - k1)
        cost = COST * S
        legs = {"short": k1, "long": k2}
    margin = max(width - credit, 1e-9)
    pnl = credit - loss - cost
    return {"credit": credit, "pnl": pnl, "margin": margin, "ret": pnl / margin, "legs": legs,
            "max_loss": margin + cost}


# ── data ─────────────────────────────────────────────────────────────────────
def _series(market, sym: str) -> Optional[pd.Series]:
    try:
        df = market.fetch_historical_data(sym, period="max", interval="1d")
        if df is None or df.empty or "Close" not in df:
            return None
        s = df["Close"].astype(float).dropna()
        idx = pd.to_datetime(s.index)
        s.index = idx.tz_localize(None) if getattr(idx, "tz", None) else idx
        return s[~s.index.duplicated()]
    except Exception as e:
        logger.warning("income lab data %s failed: %s", sym, e)
        return None


def _iv_series(close: pd.Series, vix: Optional[pd.Series], mult: float) -> Tuple[pd.Series, pd.Series]:
    rv = np.log(close).diff().rolling(20).std() * math.sqrt(252) * 1.1
    iv = rv.copy()
    src = pd.Series("realised", index=close.index)
    if vix is not None and len(vix):
        v = (vix.reindex(close.index).ffill(limit=3) / 100.0) * mult
        ok = (v > 0.05) & (v < 1.2)
        iv[ok] = v[ok]
        src[ok] = "vol index"
    return iv.clip(lower=0.06), src


def _weeks(close: pd.Series) -> List[Tuple[int, int]]:
    """(entry_pos, exit_pos) for every calendar week with at least two sessions."""
    iso = close.index.isocalendar()
    key = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values
    out, start = [], 0
    for i in range(1, len(key) + 1):
        if i == len(key) or key[i] != key[start]:
            if i - 1 > start:
                out.append((start, i - 1))
            start = i
    return out


# ── astro flags per week ──────────────────────────────────────────────────────
def _week_flags(days: List[date]) -> Dict[str, np.ndarray]:
    """Per-day boolean arrays for the astro filters, indexed like ``days``."""
    from app.services.cycles_sky import SKY
    from app.services import market_outlook as MO

    SKY.ensure()
    idx = np.array([SKY.idx(d) for d in days])
    ok = (idx >= 0) & (idx < SKY.n)
    idx = np.clip(idx, 0, SKY.n - 1)
    tithi = SKY.tithi[idx]
    amav_purn = ok & ((tithi == 15) | (tithi == 30))
    merc = ok & SKY.retro["Mercury"][idx]
    ecl_days = {e["i"] for e in SKY.events() if e["family"] == "eclipse" and "penumbral" not in e["key"]}
    ecl = np.array([i in ecl_days for i in idx]) & ok

    t = MO.table()
    cd = MO._cal_days(5)
    hist_end = MO._idx(date.today())
    zsum = None
    for spec in MO.SECTORS.values():
        wm = MO._window_mean(MO.sector_series(t, spec["rulers"]), cd)
        ref = wm[:hist_end]
        z = (wm - ref.mean()) / (ref.std() or 1e-9)
        zsum = z if zsum is None else zsum + z
    lean = zsum / len(MO.SECTORS)
    oi = np.array([MO._idx(d) for d in days])
    oi_ok = (oi >= 0) & (oi < len(lean))
    lean_d = np.where(oi_ok, lean[np.clip(oi, 0, len(lean) - 1)], 0.0)
    return {"amav_purn": amav_purn, "merc_retro": merc, "eclipse": ecl, "lean": lean_d}


# ── stats ───────────────────────────────────────────────────────────────────
def _stats(weekly: np.ndarray, dates: List[str], traded: np.ndarray, rets_on_margin: np.ndarray) -> Dict:
    eq = np.cumprod(1 + weekly)
    years = max(len(weekly) / 52.0, 1e-9)
    cagr = eq[-1] ** (1 / years) - 1 if len(eq) else 0.0
    peak = np.maximum.accumulate(eq)
    dd = float((eq / peak - 1).min()) if len(eq) else 0.0
    sd = weekly.std()
    sharpe = float((weekly.mean() - RATE / 52) / sd * math.sqrt(52)) if sd > 0 else 0.0
    months = pd.Series(weekly, index=pd.to_datetime(dates)).groupby(pd.Grouper(freq="ME")).apply(lambda r: np.prod(1 + r) - 1)
    tr = rets_on_margin[traded]
    step = max(1, len(eq) // 120)
    return {
        "weeks": int(len(weekly)), "weeks_traded": int(traded.sum()),
        "win_rate_pct": round(100 * float((tr > 0).mean()), 1) if len(tr) else None,
        "avg_week_on_margin_pct": round(100 * float(tr.mean()), 2) if len(tr) else None,
        "worst_week_on_margin_pct": round(100 * float(tr.min()), 1) if len(tr) else None,
        "cagr_pct": round(100 * cagr, 2), "max_drawdown_pct": round(100 * dd, 1), "sharpe": round(sharpe, 2),
        "positive_months_pct": round(100 * float((months > 0).mean()), 1) if len(months) else None,
        "worst_month_pct": round(100 * float(months.min()), 1) if len(months) else None,
        "equity": [{"d": dates[i], "v": round(float(eq[i]), 4)} for i in range(0, len(eq), step)] +
                  ([{"d": dates[-1], "v": round(float(eq[-1]), 4)}] if len(eq) else []),
    }


def _portfolio(rets: np.ndarray, trade: np.ndarray, risk: float) -> np.ndarray:
    idle = RATE / 52  # pledged liquid funds keep earning while posted as margin
    return np.where(trade, risk * rets, 0.0) + idle


def _cagr(weekly: np.ndarray) -> float:
    return float(np.prod(1 + weekly) ** (52 / max(len(weekly), 1)) - 1)


# ── main ────────────────────────────────────────────────────────────────────
_CACHE: Dict[str, tuple] = {}
_LOCK = threading.Lock()
_TTL = 6 * 3600.0


def run(market, symbol: str = "^NSEI", strategy: str = "put_spread", alloc: float = 0.05,
        start: str = "2009-01-01", seed: int = 7) -> Dict:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {list(STRATEGIES)}")
    alloc = min(max(alloc, 0.01), 0.25)  # share of capital at risk (max loss) per week
    key = f"{symbol}|{strategy}|{alloc}|{start}"
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]

    close = _series(market, symbol)
    if close is None or len(close) < 300:
        return {"success": False, "error": f"No price history for {symbol}; nothing simulated."}
    vix_sym = VOL_INDEX.get(symbol)
    vix = _series(market, vix_sym) if vix_sym else None
    iv, src = _iv_series(close, vix, VOL_MULT.get(symbol, 1.0))
    close = close[close.index >= pd.Timestamp(start)]
    iv, src = iv.reindex(close.index), src.reindex(close.index)

    weeks = [(a, b) for a, b in _weeks(close) if not math.isnan(iv.iloc[a])]
    px, ivs = close.values, iv.values
    rows = []
    for a, b in weeks:
        T = max(b - a, 1) / 252.0
        tr = spread_trade(px[a], px[b], T, ivs[a], strategy)
        rows.append((a, b, tr))
    if len(rows) < 52:
        return {"success": False, "error": "Not enough weekly history to back-test."}

    days_all = [d.date() for d in close.index]
    fl = _week_flags(days_all)
    rets = np.array([r[2]["ret"] for r in rows])
    dates = [str(close.index[r[1]].date()) for r in rows]
    vol_hi = np.array([ivs[r[0]] for r in rows])
    vol_thr = np.nanpercentile(vol_hi, 80)

    def any_in(arr, a, b):
        return bool(arr[a:b + 1].any())

    week_flag = {
        "none": np.zeros(len(rows), bool),
        "skip_amavasya_purnima": np.array([any_in(fl["amav_purn"], a, b) for a, b, _ in rows]),
        "skip_eclipse": np.array([any_in(fl["eclipse"], a, b) for a, b, _ in rows]),
        "skip_mercury_retro": np.array([any_in(fl["merc_retro"], a, b) for a, b, _ in rows]),
        "skip_outlook_down": np.array([(fl["lean"][a] < -0.5) if strategy != "call_spread" else (fl["lean"][a] > 0.5)
                                       for a, b, _ in rows]),
        "skip_high_vol": vol_hi >= vol_thr,
    }

    rng = np.random.default_rng(seed)
    base_trade = np.ones(len(rows), bool)
    results = []
    for f, label in FILTERS.items():
        skip = week_flag[f]
        trade = base_trade & ~skip
        weekly = _portfolio(rets, trade, alloc)
        st = _stats(weekly, dates, trade, rets)
        st.update({"key": f, "label": label, "skipped": int(skip.sum())})
        if f != "none" and 0 < skip.sum() < len(rows):
            k = int(skip.sum())
            sims = np.empty(N_RANDOM)
            for j in range(N_RANDOM):
                rs = np.zeros(len(rows), bool)
                rs[rng.choice(len(rows), k, replace=False)] = True
                sims[j] = _cagr(_portfolio(rets, ~rs, alloc))
            pct = float((sims < _cagr(weekly)).mean() * 100)
            st["vs_random_pct"] = round(pct, 1)
            st["verdict"] = ("helped beyond chance" if pct >= 95 else "hurt beyond chance" if pct <= 5
                             else "no better than skipping random weeks")
            # what happened in the skipped weeks themselves
            st["skipped_avg_week_on_margin_pct"] = round(100 * float(rets[skip].mean()), 2)
            st["skipped_win_rate_pct"] = round(100 * float((rets[skip] > 0).mean()), 1)
        else:
            st["verdict"] = "baseline" if f == "none" else "filter never or always fired"
        results.append(st)

    # this week's illustrative setup from the latest close
    S, sig = float(px[-1]), float(ivs[-1])
    today = date.today()
    nxt = [today + timedelta(days=i) for i in range(7)]
    wk_days = [d for d in nxt if d.weekday() < 5][:5]
    fl_now = _week_flags(wk_days)
    now_flags = {
        "skip_amavasya_purnima": bool(fl_now["amav_purn"].any()),
        "skip_eclipse": bool(fl_now["eclipse"].any()),
        "skip_mercury_retro": bool(fl_now["merc_retro"].any()),
        "skip_outlook_down": bool(fl_now["lean"][0] < -0.5) if strategy != "call_spread" else bool(fl_now["lean"][0] > 0.5),
        "skip_high_vol": bool(sig >= vol_thr),
    }
    setup = spread_trade(S, S, max(len(wk_days) - 1, 1) / 252.0, sig, strategy)
    helpful = [r["key"] for r in results if r.get("verdict") == "helped beyond chance"]
    fire = [k for k, v in now_flags.items() if v]
    act = [k for k in fire if k in helpful]
    if act:
        advice = "A filter that has beaten chance in the back-test fires this week (" + ", ".join(SHORT[k] for k in act) + "), so the rule says sit out this week."
    elif fire:
        advice = ("Filters firing this week: " + ", ".join(SHORT[k] for k in fire) +
                  ". None of them beat random skipping in the back-test, so they are not a reason on their own to skip.")
    else:
        advice = "No filter fires this week; the plain rule would trade as usual."

    base = results[0]
    srcs = src.value_counts().to_dict()
    name = STRATEGIES[strategy].split(' (')[0].lower()
    summary = (f"Selling {'an' if name[0] in 'aeiou' else 'a'} {name} on {symbol} every week since {dates[0][:4]} "
               f"won {base['win_rate_pct']}% of weeks and averaged {base['avg_week_on_margin_pct']}% a week on the margin used, "
               f"but {worst_phrase(base['worst_week_on_margin_pct'])}. Risking {round(alloc * 100)}% of capital "
               f"a week, the account compounded at about {base['cagr_pct']}% a year with a worst drawdown of "
               f"{abs(base['max_drawdown_pct'])}%; {base['positive_months_pct']}% of months were positive.")
    better = [r for r in results[1:] if r.get("verdict") == "helped beyond chance"]
    summary += (" Filters that beat skipping random weeks: " + ", ".join(SHORT.get(r["key"], r["label"]) for r in better) + "."
                if better else " None of the astrological filters did better than skipping the same number of random weeks.")

    out = {
        "success": True, "symbol": symbol, "strategy": strategy, "strategy_label": STRATEGIES[strategy],
        "risk_pct": round(alloc * 100, 1), "from": dates[0], "to": dates[-1],
        "vol_source": {k: int(v) for k, v in srcs.items()}, "vol_index": vix_sym,
        "results": results, "summary": summary,
        "this_week": {"spot": round(S, 2), "iv_pct": round(100 * sig, 1), "as_of": str(close.index[-1].date()),
                      "legs": {k: round(v, 1) for k, v in setup["legs"].items()},
                      "credit_pts": round(setup["credit"], 1), "max_loss_pts": round(setup["max_loss"], 1),
                      "flags": now_flags, "advice": advice},
        "method": __doc__.split("Model (stated plainly, because it is a model):")[1].split("Educational")[0].strip(),
        "disclaimer": ("Educational back-test with modelled option prices, not real fills. Past results do not "
                       "guarantee future returns; option selling can lose several weeks of income in one week. "
                       "Not financial advice."),
        "generated": datetime.utcnow().isoformat() + "Z",
    }
    with _LOCK:
        _CACHE[key] = (time.time(), out)
    return out
