"""v1.6 Market Outlook: astrology-based sector forecast + income plan by horizon.

How the forecast is built (deterministic, no hindsight):
  1. Every day, each of the nine grahas gets a transit-strength score 0..1 from its sidereal
     sign dignity (exalted / own / friendly / neutral / debilitated), minus a penalty when it is
     retrograde or combust (within 8 degrees of the Sun).
  2. Each sector is ruled by a weighted set of planets (the same rulership table the Jataka plan
     uses). Its daily score is the weighted strength of its rulers versus a neutral 0.45.
  3. For a horizon (week = 5 sessions, month = 21, year = 252) the score is averaged over the
     window ahead, then z-scored against its own 25-year history. z > +0.5 reads "up",
     z < -0.5 reads "down", anything between reads "range-bound".
  4. The same rule is replayed on each sector's real price history (non-overlapping windows) and
     its hit rate is compared with the base rate, so every call carries a verdict on whether the
     history backs it.

Options ideas follow the direction (credit spreads for income, debit spreads for a directional
bet, iron condors for range-bound) and always favour defined risk. Fund ideas are categories
plus well-known Indian ETFs, sized by the jataka's strategy fits when birth details are given.

Educational and illustrative only. Not financial advice.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import swisseph as swe

from app.services.jataka import SIGNS, _dignity
from app.services.panchang import _calc

logger = logging.getLogger(__name__)

PLANETS = {"Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
           "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}
NEUTRAL = 0.45
RETRO_PEN, COMBUST_PEN, COMBUST_ORB = 0.10, 0.15, 8.0
HORIZONS = {"week": 5, "month": 21, "year": 252}
Z_CALL = 0.5

# sector → (planet weights, price proxy, F&O names, sector ETF or None)
SECTORS: Dict[str, Dict] = {
    "Banks & financials": {"rulers": {"Jupiter": .6, "Venus": .25, "Mercury": .15}, "proxy": "^NSEBANK",
                           "fno": ["HDFCBANK", "ICICIBANK", "SBIN"], "etf": "BANKBEES"},
    "FMCG / consumer staples": {"rulers": {"Moon": .5, "Venus": .3, "Mercury": .2}, "proxy": "^CNXFMCG",
                                "fno": ["HINDUNILVR", "ITC", "NESTLEIND"], "etf": None},
    "Metals & mining": {"rulers": {"Mars": .45, "Saturn": .4, "Sun": .15}, "proxy": "^CNXMETAL",
                        "fno": ["TATASTEEL", "HINDALCO", "JSWSTEEL"], "etf": None},
    "Energy, oil & power": {"rulers": {"Sun": .4, "Mars": .35, "Saturn": .25}, "proxy": "^CNXENERGY",
                            "fno": ["RELIANCE", "ONGC", "NTPC"], "etf": None},
    "IT & telecom": {"rulers": {"Mercury": .6, "Rahu": .3, "Moon": .1}, "proxy": "^CNXIT",
                     "fno": ["INFY", "TCS", "HCLTECH"], "etf": "ITBEES"},
    "Pharma & healthcare": {"rulers": {"Moon": .3, "Ketu": .25, "Jupiter": .25, "Sun": .2}, "proxy": "^CNXPHARMA",
                            "fno": ["SUNPHARMA", "DRREDDY", "CIPLA"], "etf": None},
    "Auto": {"rulers": {"Venus": .5, "Mars": .3, "Saturn": .2}, "proxy": "^CNXAUTO",
             "fno": ["MARUTI", "M&M", "TATAMOTORS"], "etf": None},
    "Infrastructure & capital goods": {"rulers": {"Saturn": .5, "Mars": .3, "Sun": .2}, "proxy": "^CNXINFRA",
                                       "fno": ["LT", "SIEMENS", "ABB"], "etf": None},
    "Realty": {"rulers": {"Mars": .45, "Venus": .35, "Moon": .2}, "proxy": "^CNXREALTY",
               "fno": ["DLF", "GODREJPROP", "OBEROIRLTY"], "etf": None},
    "PSU / government": {"rulers": {"Sun": .6, "Saturn": .2, "Jupiter": .2}, "proxy": "^CNXPSE",
                         "fno": ["SBIN", "BEL", "COALINDIA"], "etf": "PSUBNKBEES"},
}
MARKET_PROXY = "^NSEI"

DISCLAIMER = ("Educational and illustrative only, not financial advice. Astrological sector calls are a "
              "traditional rulership model; the back-test beside each call shows whether past prices "
              "agreed. Options can lose more than expected, so use defined-risk structures, small size, "
              "and consult a SEBI-registered adviser before investing.")

# ── daily transit table ────────────────────────────────────────────────────
_T0 = date(2000, 1, 1)
_TABLE: Dict[str, np.ndarray] = {}
_TLOCK = threading.Lock()


def _jd(d: date) -> float:
    return swe.julday(d.year, d.month, d.day, 6.5)  # ~noon IST, before the Indian session closes


def _build_table(end: date) -> Dict[str, np.ndarray]:
    n = (end - _T0).days + 1
    lon = {p: np.zeros(n) for p in list(PLANETS) + ["Ketu"]}
    spd = {p: np.zeros(n) for p in lon}
    for i in range(n):
        jd = _jd(_T0 + timedelta(days=i))
        for p, pid in PLANETS.items():
            lon[p][i], spd[p][i] = _calc(jd, pid)
        lon["Ketu"][i], spd["Ketu"][i] = (lon["Rahu"][i] + 180.0) % 360.0, spd["Rahu"][i]
    out: Dict[str, np.ndarray] = {}
    for p in lon:
        sign = (lon[p] // 30).astype(int)
        base = np.array([_dignity(p, int(s), float(l % 30))[1] for s, l in zip(sign, lon[p])])
        if p not in ("Rahu", "Ketu", "Sun", "Moon"):
            base = base - RETRO_PEN * (spd[p] < 0)
        if p not in ("Sun", "Rahu", "Ketu"):
            sep = np.abs(((lon[p] - lon["Sun"]) + 180.0) % 360.0 - 180.0)
            base = base - COMBUST_PEN * (sep < COMBUST_ORB)
        out[p] = base
        out[p + ":sign"] = sign
        out[p + ":retro"] = spd[p] < 0
        out[p + ":lon"] = lon[p]
    out["_n"] = np.array([n])
    return out


def table() -> Dict[str, np.ndarray]:
    end = date.today() + timedelta(days=420)
    with _TLOCK:
        if not _TABLE or int(_TABLE["_n"][0]) < (end - _T0).days - 30:
            _TABLE.clear()
            _TABLE.update(_build_table(end))
        return _TABLE


def _idx(d: date) -> int:
    return (d - _T0).days


def sector_series(t: Dict[str, np.ndarray], rulers: Dict[str, float]) -> np.ndarray:
    tot = sum(rulers.values())
    return sum(w * (t[p] - NEUTRAL) for p, w in rulers.items()) / tot


def _window_mean(s: np.ndarray, cal_days: int) -> np.ndarray:
    """Forward mean over the next ``cal_days`` calendar days for every start day."""
    c = np.concatenate([[0.0], np.cumsum(s)])
    n = len(s)
    j = np.minimum(np.arange(n) + cal_days, n)
    return (c[j] - c[:n]) / np.maximum(j - np.arange(n), 1)


def _cal_days(sessions: int) -> int:
    return max(1, int(round(sessions * 7 / 5)))


# ── drivers text ────────────────────────────────────────────────────────────
def _status(t, p: str, i: int) -> Dict:
    sign = int(t[p + ":sign"][i])
    dig = _dignity(p, sign, float(t[p + ":lon"][i] % 30))[0]
    bits = [f"{dig} in {SIGNS[sign]}"] if dig not in ("neutral", "neutral node") else [f"in {SIGNS[sign]}"]
    if p not in ("Rahu", "Ketu", "Sun", "Moon") and bool(t[p + ":retro"][i]):
        bits.append("retrograde")
    if p not in ("Sun", "Rahu", "Ketu"):
        sep = abs(((t[p + ":lon"][i] - t["Sun:lon"][i]) + 180.0) % 360.0 - 180.0)
        if sep < COMBUST_ORB:
            bits.append("combust")
    return {"planet": p, "state": ", ".join(bits), "score": round(float(t[p][i]), 2),
            "effect": "+" if t[p][i] > NEUTRAL + 0.05 else ("−" if t[p][i] < NEUTRAL - 0.05 else "·")}


def _window_status(t, p: str, i0: int, i1: int) -> Dict:
    """How a ruler spends the window: the sign it occupies longest and its average strength."""
    i1 = min(i1, len(t[p]) - 1)
    span = i1 - i0 + 1
    if p in FAST and span >= FAST[p]:
        avg = float(np.mean(t[p][i0:i1 + 1]))
        return {"planet": p, "state": "moves through several signs, so its effect averages out",
                "score": round(avg, 2), "effect": "·"}
    signs = t[p + ":sign"][i0:i1 + 1]
    main = int(np.bincount(signs, minlength=12).argmax())
    j = i0 + int(np.argmax(signs == main))
    st = _status(t, p, j)
    retro = float(np.mean(t[p + ":retro"][i0:i1 + 1])) if p not in ("Rahu", "Ketu", "Sun", "Moon") else 0.0
    if span > 7:
        st["state"] = st["state"].replace(", retrograde", "").replace(", combust", "")
        if retro > 0.3:
            st["state"] += f", retrograde {round(100 * retro)}% of the time"
    counts = np.bincount(signs, minlength=12)
    for sg in np.argsort(-counts):
        sg = int(sg)
        if sg == main or counts[sg] < 0.15 * span:
            continue
        dig = _dignity(p, sg, 15.0)[0]
        if dig in ("exalted", "debilitated", "own sign", "moolatrikona"):
            st["state"] += f"; {dig} in {SIGNS[sg]} {round(100 * counts[sg] / span)}% of the time"
    avg = float(np.mean(t[p][i0:i1 + 1]))
    st["score"] = round(avg, 2)
    st["effect"] = "+" if avg > NEUTRAL + 0.05 else ("−" if avg < NEUTRAL - 0.05 else "·")
    return st


FAST = {"Moon": 20, "Sun": 120, "Mercury": 120, "Venus": 200}  # window (days) after which it averages out
SLOW_ONLY = ("Jupiter", "Saturn", "Rahu", "Ketu", "Mars")


def _changes(t, p: str, i0: int, i1: int) -> List[str]:
    out = []
    s, r = t[p + ":sign"], t[p + ":retro"]
    for i in range(i0 + 1, min(i1, len(s) - 1) + 1):
        d = (_T0 + timedelta(days=i)).isoformat()
        if s[i] != s[i - 1]:
            out.append(f"{p} enters {SIGNS[int(s[i])]} on {d}")
        elif p not in ("Rahu", "Ketu", "Sun", "Moon") and r[i] != r[i - 1]:
            out.append(f"{p} turns {'retrograde' if r[i] else 'direct'} on {d}")
    return out


# ── back-test ───────────────────────────────────────────────────────────────
def backtest(close: pd.Series, zs: np.ndarray, sessions: int) -> Dict:
    """Replay the call rule on non-overlapping windows of real prices."""
    close = close.dropna()
    close = close[close.index.date >= _T0] if len(close) else close
    if len(close) < sessions * 8:
        return {"n": 0, "verdict": "not enough price history to test"}
    px = close.values.astype(float)
    days = np.array([_idx(d) for d in close.index.date])
    starts = np.arange(0, len(px) - sessions, sessions)
    fwd = px[starts + sessions] / px[starts] - 1.0
    z = zs[np.clip(days[starts], 0, len(zs) - 1)]
    up_base = float(np.mean(fwd > 0))
    calls = np.where(z > Z_CALL, 1, np.where(z < -Z_CALL, -1, 0))
    m = calls != 0
    n = int(m.sum())
    if n < 6:
        return {"n": n, "windows": int(len(starts)), "verdict": "too few calls to judge",
                "base_up_pct": round(100 * up_base, 1)}
    hit = ((calls[m] > 0) & (fwd[m] > 0)) | ((calls[m] < 0) & (fwd[m] <= 0))
    p = np.where(calls[m] > 0, up_base, 1 - up_base)
    exp, var = float(p.sum()), float((p * (1 - p)).sum())
    zstat = (float(hit.sum()) - exp) / math.sqrt(var) if var > 0 else 0.0
    up_ret = fwd[calls > 0].mean() if (calls > 0).any() else float("nan")
    dn_ret = fwd[calls < 0].mean() if (calls < 0).any() else float("nan")
    if zstat >= 1.96:
        verdict = "significant edge"
    elif zstat >= 1.0:
        verdict = "weak hint"
    elif zstat <= -1.96:
        verdict = "worked in reverse"
    else:
        verdict = "no edge (noise)"
    return {"n": n, "windows": int(len(starts)), "hit_pct": round(100 * float(hit.mean()), 1),
            "expected_pct": round(100 * exp / n, 1), "z": round(zstat, 2), "verdict": verdict,
            "base_up_pct": round(100 * up_base, 1),
            "avg_ret_up_calls_pct": None if math.isnan(up_ret) else round(100 * float(up_ret), 2),
            "avg_ret_down_calls_pct": None if math.isnan(dn_ret) else round(100 * float(dn_ret), 2),
            "since": str(close.index[0].date())}


# ── options idea ─────────────────────────────────────────────────────────────
def options_idea(sector: str, direction: str, horizon: str, verdict: str) -> Dict:
    spec = SECTORS.get(sector, {})
    names = ", ".join(spec.get("fno", [])[:2]) or "the sector's F&O stocks"
    if horizon == "week":
        und = "Nifty 50 weekly options (stock options expire monthly)"
    elif sector == "Banks & financials":
        und = "Bank Nifty monthly options"
    else:
        und = f"monthly stock options on {names}"
    if horizon == "year":
        sell = {"up": f"Overweight the sector ({spec.get('etf') or 'a sector index fund'}) and sell monthly covered calls on {names} if held",
                "down": "Underweight or avoid the sector; no year-long short is advisable for retail",
                "range": "Hold at market weight; collect income with monthly covered calls"}[direction]
        buy = {"up": "Accumulate on dips through the year (SIP style)",
               "down": "Wait for the outlook to turn before adding",
               "range": "No directional bet"}[direction]
    else:
        sell = {"up": f"Sell a bull put spread (short put ~0.20 delta, long put 1–2 strikes lower) on {und}",
                "down": f"Sell a bear call spread (short call ~0.20 delta, long call 1–2 strikes higher) on {und}",
                "range": f"Sell an iron condor with ~0.15-delta short strikes on {und}"}[direction]
        buy = {"up": f"Or buy a bull call debit spread on {und}; the most you can lose is the premium paid",
               "down": f"Or buy a bear put debit spread on {und}; the most you can lose is the premium paid",
               "range": "Avoid buying options: time decay works against buyers in a range"}[direction]
    trust = ("History backs this rule for this sector, so it can be used at normal small size."
             if verdict == "significant edge" else
             "History only weakly backs this, so keep size small." if verdict == "weak hint" else
             "History does not back this call, so treat it as an astrological view only: skip it or use the smallest size.")
    return {"income": sell, "directional": buy, "trust": trust}


# ── fund / income plan ───────────────────────────────────────────────────────
INCOME_BUCKETS = {
    "week": {
        "label": "Weekly income",
        "how": "Defined-risk premium selling on Nifty weekly expiries, with the margin money parked in a liquid ETF so it keeps earning.",
        "ideas": [
            {"name": "Nifty weekly credit spreads / iron condors", "kind": "options", "yield": "≈12–25% a year on margin used, with occasional sharp losing weeks"},
            {"name": "LIQUIDBEES (liquid ETF) as margin collateral", "kind": "ETF", "yield": "≈ overnight rate, 6–6.5%"},
        ],
        "risk": "High: gap moves and event weeks (budget, RBI, elections) can wipe out several weeks of premium.",
        "strategy_key": "options_selling",
    },
    "month": {
        "label": "Monthly income",
        "how": "A systematic withdrawal plan (SWP) from lower-volatility hybrid and debt funds, topped up by monthly covered calls if you hold F&O stocks.",
        "ideas": [
            {"name": "Arbitrage fund", "kind": "mutual fund category", "yield": "≈6.5–7.5%, very low volatility, equity taxation"},
            {"name": "Equity savings fund (SWP)", "kind": "mutual fund category", "yield": "≈7–9% over long periods"},
            {"name": "Balanced advantage / dynamic asset allocation fund (SWP)", "kind": "mutual fund category", "yield": "≈8–11% over long periods, can dip 10–15%"},
            {"name": "Corporate bond / PSU bond fund", "kind": "mutual fund category", "yield": "≈7–8%, interest-rate sensitive"},
        ],
        "risk": "Low to medium: values move month to month, but no single month can blow up the plan.",
        "strategy_key": "fixed_income",
    },
    "year": {
        "label": "Yearly growth & income",
        "how": "A low-cost index core with a gold hedge, tilted toward the sectors the outlook favours for the year.",
        "ideas": [
            {"name": "NIFTYBEES (Nifty 50 ETF) core", "kind": "ETF", "yield": "long-run ≈10–12% a year, with down years"},
            {"name": "JUNIORBEES (Nifty Next 50 ETF)", "kind": "ETF", "yield": "higher growth, higher swings"},
            {"name": "GOLDBEES (gold ETF) hedge, 10–15%", "kind": "ETF", "yield": "tends to hold up when equities fall"},
        ],
        "risk": "Medium: equity can fall 20–35% in a bad year; needs a 5-year view.",
        "strategy_key": "long_term_equity",
    },
}
DEFAULT_SPLIT = {"week": 0.2, "month": 0.4, "year": 0.4}


def income_plan(sectors_by_h: Dict[str, List[Dict]], jataka_plan: Optional[Dict], capital: float) -> Dict:
    fits = {}
    if jataka_plan and jataka_plan.get("strategies"):
        by = {s["key"]: s["fit"] for s in jataka_plan["strategies"]}
        fits = {h: float(by.get(b["strategy_key"], 50)) for h, b in INCOME_BUCKETS.items()}
    if fits:
        raw = {h: max(f - 25.0, 5.0) for h, f in fits.items()}
        tot = sum(raw.values())
        split = {h: v / tot for h, v in raw.items()}
        split["week"] = min(split["week"], 0.30)  # premium selling never more than 30% of capital
        rest = 1 - split["week"]
        mt = split["month"] + split["year"]
        split["month"], split["year"] = rest * split["month"] / mt, rest * split["year"] / mt
    else:
        split = dict(DEFAULT_SPLIT)
    natal = [s["name"] for s in (jataka_plan or {}).get("sectors", [])[:4]]
    out = []
    for h, b in INCOME_BUCKETS.items():
        ideas = [dict(i) for i in b["ideas"]]
        if h == "year":
            ups = [s for s in sectors_by_h.get("year", []) if s["direction"] == "up"]
            for s in ups[:2]:
                etf = SECTORS[s["sector"]]["etf"]
                ideas.append({"name": f"Tilt: {etf + ' (' + s['sector'] + ' ETF)' if etf else s['sector'] + ' index fund'}",
                              "kind": "ETF" if etf else "index fund",
                              "yield": f"outlook up for the year (z {s['z']:+.1f}, back-test: {s['backtest'].get('verdict')})"})
        bias = None
        if h in ("week", "month"):
            mk = sectors_by_h.get(h, [])
            score = float(np.mean([s["z"] for s in mk])) if mk else 0.0
            bias = "up" if score > Z_CALL / 2 else ("down" if score < -Z_CALL / 2 else "range")
        out.append({"horizon": h, "label": b["label"], "how": b["how"], "ideas": ideas, "risk": b["risk"],
                    "allocation_pct": round(100 * split[h]), "amount": round(capital * split[h]),
                    "chart_fit": round(fits[h]) if fits else None,
                    "market_bias": bias})
    picks = []
    if natal:
        for h in ("month", "year"):
            for s in sectors_by_h.get(h, []):
                if s["direction"] == "up" and any(_same_sector(s["sector"], n) for n in natal):
                    picks.append({"horizon": h, "sector": s["sector"], "why": "your chart favours it and transits are supportive"})
    return {"buckets": out, "split_source": "your chart's strategy fits" if fits else "a balanced default",
            "personal_picks": picks, "natal_sectors": natal}


NATAL_NAME = {  # market_outlook sector -> jataka_plan sector name prefix
    "Banks & financials": "BFSI", "FMCG / consumer staples": "FMCG", "Metals & mining": "Metals",
    "Energy, oil & power": "Metals", "IT & telecom": "IT /", "Pharma & healthcare": "Pharma",
    "Auto": "Auto", "Infrastructure & capital goods": "Infrastructure", "Realty": "Realty",
    "PSU / government": "PSU",
}


def _same_sector(a: str, b: str) -> bool:
    k = NATAL_NAME.get(a)
    return bool(k) and b.startswith(k)


# ── main entry ─────────────────────────────────────────────────────────────
_PX_CACHE: Dict[str, tuple] = {}
_PX_TTL = 6 * 3600.0


def _history(market, symbol: str) -> Optional[pd.Series]:
    hit = _PX_CACHE.get(symbol)
    if hit and time.time() - hit[0] < _PX_TTL:
        return hit[1]
    try:
        df = market.fetch_historical_data(symbol, period="max", interval="1d")
        s = df["Close"].astype(float) if df is not None and not df.empty and "Close" in df else None
    except Exception as e:  # missing data simply means "not tested"
        logger.warning("outlook history %s failed: %s", symbol, e)
        s = None
    if s is not None:
        s.index = pd.to_datetime(s.index).tz_localize(None) if getattr(s.index, "tz", None) else pd.to_datetime(s.index)
    _PX_CACHE[symbol] = (time.time(), s)
    return s


def outlook(market, start: Optional[date] = None, jataka_plan: Optional[Dict] = None,
            capital: float = 500000.0) -> Dict:
    t = table()
    start = start or date.today()
    i0 = _idx(start)
    hist_end = _idx(date.today())
    syms = [SECTORS[s]["proxy"] for s in SECTORS] + [MARKET_PROXY]
    with ThreadPoolExecutor(max_workers=6) as ex:
        px = dict(zip(syms, ex.map(lambda s: _history(market, s), syms)))

    by_h: Dict[str, List[Dict]] = {}
    for h, sessions in HORIZONS.items():
        cd = _cal_days(sessions)
        rows = []
        for name, spec in SECTORS.items():
            s = sector_series(t, spec["rulers"])
            wm = _window_mean(s, cd)
            ref = wm[:hist_end]
            mu, sd = float(ref.mean()), float(ref.std()) or 1e-9
            zs = (wm - mu) / sd
            z = float(zs[i0])
            direction = "up" if z > Z_CALL else ("down" if z < -Z_CALL else "range")
            drivers = [_window_status(t, p, i0, i0 + cd - 1) for p in sorted(spec["rulers"], key=lambda p: -spec["rulers"][p])]
            movers = [p for p in spec["rulers"] if p != "Moon" and (cd < 120 or p in SLOW_ONLY)]
            changes = sorted((c for p in movers for c in _changes(t, p, i0, i0 + cd)), key=lambda c: c[-10:])[:4]
            close = px.get(spec["proxy"])
            bt = backtest(close, zs, sessions) if close is not None else {"n": 0, "verdict": "no price data for the proxy"}
            rows.append({"sector": name, "z": round(z, 2), "direction": direction,
                         "strength_pct": round(50 + 50 * math.tanh(z / 2)), "drivers": drivers, "changes": changes,
                         "proxy": spec["proxy"], "fno": spec["fno"], "etf": spec["etf"], "backtest": bt,
                         "options": options_idea(name, direction, h, bt.get("verdict", ""))})
        rows.sort(key=lambda r: -r["z"])
        by_h[h] = rows

    def summary(h: str) -> str:
        rows = by_h[h]
        ups = [r["sector"] for r in rows if r["direction"] == "up"]
        dns = [r["sector"] for r in rows if r["direction"] == "down"][::-1]
        backed = [r["sector"] for r in rows if r["direction"] != "range" and r["backtest"].get("verdict") in ("significant edge", "weak hint")]
        span = {"week": "this week", "month": "over the next month", "year": "over the next year"}[h]
        txt = (f"Astrologically, {span} the strongest sectors are {', '.join(ups[:3]) or 'none in particular'} "
               f"and the weakest are {', '.join(dns[:3]) or 'none in particular'}.")
        txt += (f" Past prices gave at least some support to the calls on {', '.join(backed[:3])}." if backed else
                " None of these calls has reliable support in past prices, so read them as an astrological view, not a statistical edge.")
        return txt

    return {"success": True, "as_of": start.isoformat(), "horizons": {h: {"sessions": HORIZONS[h], "sectors": by_h[h], "summary": summary(h)} for h in HORIZONS},
            "income_plan": income_plan(by_h, jataka_plan, capital),
            "method": __doc__.split("How the forecast is built (deterministic, no hindsight):")[1].split("Educational")[0].strip(),
            "disclaimer": DISCLAIMER, "generated": datetime.now(timezone.utc).isoformat()}
