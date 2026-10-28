"""
Stock × Kundli (v1.3) — data-backed correlation between the selected stock and
the jataka's birth chart.

1. Dasha periods  : stock returns during each of the native's Vimshottari MD / AD
                    (and PDs aggregated by lord) since birth.
2. Transit→natal  : over the stock's FULL history, 20-trading-day forward returns
                    on days when transiting Jupiter / Saturn / Rahu / Mars
                    conjoin or cast a Vedic (whole-sign) aspect on the native's
                    Moon, Lagna, Sun, 2nd lord and 11th lord (+ Sade Sati), versus
                    the stock's unconditional baseline; then which of those are
                    active now / start in the next 90 days.
3. Synastry       : the stock/index "birth chart" (known launch/listing date, else
                    the first trading date in the dataset) against the natal chart.
4. Verdict        : plain-English fit score + entries / sizing / timing windows.

Vectorised: one ephemeris pass per trading day (cached by date range), numpy
searchsorted for period slicing. Honest by design — every statistic carries its
sample size and nothing is shown as significant when it is not.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import swisseph as swe

from app.core.vedic import AYANAMSA_MODES, NODE_TYPES, sidereal_mode
from app.services.astro_data import SIGN_LORDS
from app.services.dasha import LORD_THEMES

logger = logging.getLogger(__name__)

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
FWD = 20  # forward window (trading days ≈ 1 month)

# Known index launch / listing dates ("birth" of the instrument) — noon local exchange time.
STOCK_BIRTHS = {
    "^GSPC": ("1957-03-04", "S&P 500 launched as a 500-stock index", "America/New_York"),
    "^DJI": ("1896-05-26", "Dow Jones Industrial Average first published", "America/New_York"),
    "^IXIC": ("1971-02-05", "NASDAQ Composite launched", "America/New_York"),
    "^NDX": ("1985-01-31", "NASDAQ-100 launched", "America/New_York"),
    "^FTSE": ("1984-01-03", "FTSE 100 launched (base 1000)", "Europe/London"),
    "^NSEI": ("1996-04-22", "Nifty 50 launched on NSE", "Asia/Kolkata"),
    "^BSESN": ("1986-01-02", "BSE Sensex first compiled", "Asia/Kolkata"),
    "^NSEBANK": ("2000-09-15", "Nifty Bank launched", "Asia/Kolkata"),
    "^N225": ("1950-09-07", "Nikkei 225 first calculated", "Asia/Tokyo"),
    "^GDAXI": ("1988-07-01", "DAX launched", "Europe/Berlin"),
    "AAPL": ("1980-12-12", "Apple IPO on NASDAQ", "America/New_York"),
    "MSFT": ("1986-03-13", "Microsoft IPO", "America/New_York"),
    "AMZN": ("1997-05-15", "Amazon IPO", "America/New_York"),
    "GOOGL": ("2004-08-19", "Google IPO", "America/New_York"),
    "META": ("2012-05-18", "Facebook IPO", "America/New_York"),
    "NVDA": ("1999-01-22", "NVIDIA IPO", "America/New_York"),
    "TSLA": ("2010-06-29", "Tesla IPO", "America/New_York"),
    "RELIANCE.NS": ("1977-11-20", "Reliance Industries listing (approx.)", "Asia/Kolkata"),
    "TCS.NS": ("2004-08-25", "TCS listing on NSE/BSE", "Asia/Kolkata"),
    "INFY.NS": ("1993-06-14", "Infosys listing", "Asia/Kolkata"),
    "HDFCBANK.NS": ("1995-05-19", "HDFC Bank listing (approx.)", "Asia/Kolkata"),
}

TRANSIT_PLANETS = {"Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Mars": swe.MARS, "Rahu": None}
# Vedic special aspects (house counted from the transiting planet, 1 = conjunction)
DRISHTI = {"Jupiter": {5, 7, 9}, "Saturn": {3, 7, 10}, "Mars": {4, 7, 8}, "Rahu": {5, 7, 9}}
BENEFIC = {"Jupiter", "Venus", "Mercury", "Moon"}


# ───────────────────────── ephemeris over a date index ─────────────────────────
@lru_cache(maxsize=16)
def _transit_lons(start: str, n_days: int, ayanamsa: str, node: str) -> Dict[str, np.ndarray]:
    """Daily (00:00 UT) sidereal longitudes for the transit planets over a calendar range."""
    mode = AYANAMSA_MODES.get(ayanamsa, AYANAMSA_MODES["lahiri"])[0]
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if mode is not None else 0)
    d0 = datetime.fromisoformat(start)
    jd0 = swe.julday(d0.year, d0.month, d0.day, 0.0)
    out = {k: np.empty(n_days) for k in TRANSIT_PLANETS}
    nid = NODE_TYPES.get(node, swe.MEAN_NODE)
    with sidereal_mode(mode):
        for i in range(n_days):
            jd = jd0 + i
            for k, pid in TRANSIT_PLANETS.items():
                out[k][i] = swe.calc_ut(jd, nid if pid is None else pid, flags)[0][0]
    return out


def _lons_for(dates: pd.DatetimeIndex, ayanamsa: str, node: str) -> Dict[str, np.ndarray]:
    start = dates[0].normalize()
    n = int((dates[-1].normalize() - start).days) + 1
    cal = _transit_lons(start.strftime("%Y-%m-%d"), n, ayanamsa, node)
    idx = (dates.normalize() - start).days.values.astype(int)
    return {k: v[idx] for k, v in cal.items()}


def _sf(x, nd=4):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(v) or math.isinf(v)) else round(v, nd)


# ───────────────────────── 1. dasha period performance ─────────────────────────
def _period_stats(close: pd.Series, weekly: pd.Series, start: datetime, end: datetime) -> Optional[Dict]:
    idx = close.index
    i0 = idx.searchsorted(pd.Timestamp(start))
    i1 = idx.searchsorted(pd.Timestamp(end)) - 1
    if i1 - i0 < 5:
        return None
    seg = close.values[i0:i1 + 1]
    lr = np.diff(np.log(seg))
    n = len(lr)
    tot = float(np.log(seg[-1] / seg[0]))
    ann = math.exp(tot * 252.0 / n) - 1.0
    vol = float(np.std(lr, ddof=1) * math.sqrt(252)) if n > 2 else 0.0
    w = weekly[(weekly.index >= pd.Timestamp(start)) & (weekly.index < pd.Timestamp(end))]
    hit = float((w > 0).mean()) if len(w) >= 3 else float((lr > 0).mean())
    return {"days": int(n), "total_return": _sf(math.exp(tot) - 1), "ann_return": _sf(ann),
            "vol": _sf(vol), "hit_rate": _sf(hit, 3),
            "from": idx[i0].strftime("%Y-%m-%d"), "to": idx[i1].strftime("%Y-%m-%d")}


def dasha_performance(close: pd.Series, dasha, now: datetime) -> Dict:
    weekly = np.log(close.resample("W-FRI").last().dropna()).diff().dropna()
    mds, ads, pds = [], [], []
    for md in dasha.tree:
        if md["start"] > now:
            break
        st = _period_stats(close, weekly, md["start"], min(md["end"], now))
        if st:
            mds.append({"lord": md["lord"], "start": md["start"].strftime("%Y-%m-%d"),
                        "end": md["end"].strftime("%Y-%m-%d"), "running": md["end"] > now, **st})
        for ad in md["antardashas"]:
            if ad["start"] > now:
                break
            st = _period_stats(close, weekly, ad["start"], min(ad["end"], now))
            if st:
                ads.append({"md": md["lord"], "lord": ad["lord"], "label": f"{md['lord']}/{ad['lord']}",
                            "start": ad["start"].strftime("%Y-%m-%d"), "end": ad["end"].strftime("%Y-%m-%d"),
                            "running": ad["end"] > now, **st})
            for pd_ in ad["pratyantardashas"]:
                if pd_["start"] > now:
                    break
                st = _period_stats(close, weekly, pd_["start"], min(pd_["end"], now))
                if st:
                    pds.append({"lord": pd_["lord"], **st})

    def by_lord(rows: List[Dict]) -> List[Dict]:
        agg: Dict[str, Dict] = {}
        for r in rows:
            a = agg.setdefault(r["lord"], {"lord": r["lord"], "n": 0, "days": 0, "_lr": 0.0, "_hit": 0.0, "_vol2": 0.0})
            a["n"] += 1
            a["days"] += r["days"]
            a["_lr"] += math.log1p(r["total_return"] or 0.0)
            a["_hit"] += (r["hit_rate"] or 0) * r["days"]
            a["_vol2"] += (r["vol"] or 0) ** 2 * r["days"]
        out = []
        for a in agg.values():
            d = max(1, a["days"])
            out.append({"lord": a["lord"], "periods": a["n"], "days": a["days"],
                        "ann_return": _sf(math.exp(a["_lr"] * 252.0 / d) - 1),
                        "hit_rate": _sf(a["_hit"] / d, 3), "vol": _sf(math.sqrt(a["_vol2"] / d))})
        out.sort(key=lambda r: -(r["ann_return"] or -9))
        return out

    ad_lord, pd_lord = by_lord(ads), by_lord(pds)
    base = _period_stats(close, weekly, max(dasha.birth, close.index[0].to_pydatetime()), now)
    plain = ""
    if ad_lord:
        best, worst = ad_lord[0], ad_lord[-1]
        plain = (f"Since your birth this stock rose fastest during your {best['lord']} antardashas "
                 f"({best['ann_return']*100:+.1f}%/yr over {best['periods']} period(s)) and did worst in "
                 f"{worst['lord']} antardashas ({worst['ann_return']*100:+.1f}%/yr)"
                 + (f", versus {base['ann_return']*100:+.1f}%/yr overall." if base else "."))
        if pd_lord:
            plain += (f" At the finer pratyantardasha level, {pd_lord[0]['lord']} weeks were best "
                      f"({pd_lord[0]['ann_return']*100:+.1f}%/yr) and {pd_lord[-1]['lord']} weeks worst.")
    return {"mahadashas": mds, "antardashas": ads, "ad_by_lord": ad_lord, "pd_by_lord": pd_lord,
            "baseline": base, "plain": plain,
            "note": ("Periods start at your birth; the stock's earlier history is used only in the transit study. "
                     "Few periods per lord → treat as anecdotal, not statistically proven.")}


# ───────────────────────── 2. transit → natal ─────────────────────────
def _natal_points(positions: Dict, lag: int) -> Dict[str, Tuple[int, str]]:
    l2, l11 = SIGN_LORDS[(lag + 1) % 12], SIGN_LORDS[(lag + 10) % 12]
    raw = {
        "Moon": (positions["Moon"]["sign_number"], "natal Moon (mind, mood)"),
        "Lagna": (lag, "Lagna (self)"),
        "Sun": (positions["Sun"]["sign_number"], "natal Sun (confidence, authority)"),
        f"2nd lord {l2}": (positions[l2]["sign_number"], "2nd lord (savings)"),
        f"11th lord {l11}": (positions[l11]["sign_number"], "11th lord (gains)"),
    }
    # points sharing a sign give identical whole-sign contacts → merge them
    merged: Dict[int, Tuple[List[str], List[str]]] = {}
    for name, (sign, label) in raw.items():
        names, labels = merged.setdefault(sign, ([], []))
        names.append(name)
        labels.append(label)
    return {" & ".join(n): (sg, " + ".join(lb)) for sg, (n, lb) in merged.items()}


def _run_window(fm: np.ndarray, dates: pd.DatetimeIndex) -> Optional[Dict]:
    """First contiguous active run inside the 90-day window."""
    if not fm.any():
        return None
    i0 = int(np.argmax(fm))
    off = np.where(~fm[i0:])[0]
    i1 = i0 + int(off[0]) - 1 if len(off) else len(fm) - 1
    return {"from": dates[i0].strftime("%Y-%m-%d"), "to": dates[i1].strftime("%Y-%m-%d"),
            "until_after_window": bool(i1 == len(fm) - 1)}


def _contact_masks(sign_arr: np.ndarray, planet: str, natal_sign: int) -> Dict[str, np.ndarray]:
    rel = (natal_sign - sign_arr) % 12 + 1  # house of natal point counted from the transit planet
    m = {"conjunct": rel == 1}
    asp = np.zeros_like(rel, dtype=bool)
    for h in DRISHTI[planet]:
        asp |= rel == h
    m["aspects"] = asp
    return m


def transit_study(close: pd.Series, positions: Dict, lag: int, ayanamsa: str, node: str,
                  now: datetime) -> Dict:
    dates = close.index
    lons = _lons_for(dates, ayanamsa, node)
    logc = np.log(close.values)
    fwd = np.full(len(logc), np.nan)
    fwd[:-FWD] = logc[FWD:] - logc[:-FWD]
    valid = ~np.isnan(fwd)
    base_mean = float(np.nanmean(fwd))
    base_std = float(np.nanstd(fwd))
    base_hit = float((fwd[valid] > 0).mean())

    # forward calendar for "now / next 90 days"
    fut_dates = pd.date_range(pd.Timestamp(now.date()), periods=91, freq="D")
    fut = _lons_for(fut_dates, ayanamsa, node)

    points = _natal_points(positions, lag)
    rows = []
    for planet in TRANSIT_PLANETS:
        sgn = (lons[planet] // 30).astype(int)
        fsgn = (fut[planet] // 30).astype(int)
        for pname, (nsign, plabel) in points.items():
            masks = _contact_masks(sgn, planet, nsign)
            fmasks = _contact_masks(fsgn, planet, nsign)
            for ctype, m in masks.items():
                mm = m & valid
                n = int(mm.sum())
                if n < 40:
                    continue
                r = fwd[mm]
                mean = float(r.mean())
                n_eff = max(1.0, n / FWD)
                t = (mean - base_mean) / (base_std / math.sqrt(n_eff)) if base_std > 0 else 0.0
                fm = fmasks[ctype]
                active_now = bool(fm[0])
                window = _run_window(fm, fut_dates)
                rows.append({
                    "transit": planet, "natal": pname, "natal_label": plabel, "contact": ctype,
                    "label": f"{planet} {'on' if ctype == 'conjunct' else 'aspecting'} {pname}",
                    "days": n, "fwd_mean_pct": _sf(mean * 100, 2), "edge_pct": _sf((mean - base_mean) * 100, 2),
                    "hit_rate": _sf((r > 0).mean(), 3), "t_stat": _sf(t, 2),
                    "verdict": "better" if t >= 1.5 else "worse" if t <= -1.5 else "no clear edge",
                    "active_now": active_now, "window_90d": window,
                })
    # Sade Sati: Saturn in 12th/1st/2nd from natal Moon
    ms = positions["Moon"]["sign_number"]
    s_sgn = (lons["Saturn"] // 30).astype(int)
    rel = (s_sgn - ms) % 12
    ss = np.isin(rel, [11, 0, 1]) & valid
    if ss.sum() >= 40:
        r = fwd[ss]
        mean = float(r.mean())
        n_eff = max(1.0, ss.sum() / FWD)
        t = (mean - base_mean) / (base_std / math.sqrt(n_eff)) if base_std > 0 else 0.0
        frel = ((fut["Saturn"] // 30).astype(int) - ms) % 12
        fss = np.isin(frel, [11, 0, 1])
        rows.append({"transit": "Saturn", "natal": "Moon", "natal_label": "Sade Sati (Saturn 12th/1st/2nd from Moon)",
                     "contact": "sade_sati", "label": "Sade Sati (Saturn around your Moon)", "days": int(ss.sum()),
                     "fwd_mean_pct": _sf(mean * 100, 2), "edge_pct": _sf((mean - base_mean) * 100, 2),
                     "hit_rate": _sf((r > 0).mean(), 3), "t_stat": _sf(t, 2),
                     "verdict": "better" if t >= 1.5 else "worse" if t <= -1.5 else "no clear edge",
                     "active_now": bool(fss[0]),
                     "window_90d": _run_window(fss, fut_dates)})
    rows.sort(key=lambda r: -(r["edge_pct"] or 0))
    active = [r for r in rows if r["active_now"]]
    upcoming = [r for r in rows if not r["active_now"] and r["window_90d"]]
    better = [r for r in rows if r["verdict"] == "better"]
    worse = [r for r in rows if r["verdict"] == "worse"]
    act_edge = float(np.mean([r["edge_pct"] for r in active])) if active else 0.0
    plain = (f"Across {len(close):,} trading days the stock's average 1-month forward return was "
             f"{base_mean*100:+.2f}% ({base_hit*100:.0f}% of months up). "
             + (f"Historically better when: {', '.join(r['label'] for r in better[:3])}. " if better else
                "No transit contact showed a statistically clear positive edge. ")
             + (f"Historically worse when: {', '.join(r['label'] for r in worse[-3:])}. " if worse else "")
             + (f"Active now: {', '.join(r['label'] for r in active[:4])} — their average historical edge is "
                f"{act_edge:+.2f} pts/month." if active else "No studied contact is active today."))
    return {"rows": rows, "active_now": active, "upcoming": upcoming,
            "baseline": {"fwd_mean_pct": _sf(base_mean * 100, 2), "hit_rate": _sf(base_hit, 3), "days": int(valid.sum())},
            "active_edge_pct": _sf(act_edge, 2), "plain": plain,
            "method": ("Vedic whole-sign gochara: conjunction = same sign; aspects = Jupiter/Rahu 5-7-9, Saturn 3-7-10, "
                       "Mars 4-7-8 counted from the transiting planet. Edge = mean 20-day forward log-return on contact days "
                       "minus the all-days mean; t-stat uses n/20 effective samples for overlap. |t| ≥ 1.5 is flagged.")}


# ───────────────────────── 3. synastry ─────────────────────────
def _stock_chart(symbol: str, first_date: str, ayanamsa: str, node: str) -> Dict:
    from app.services.jataka_geo import local_to_utc
    from app.core.vedic import sky_positions
    if symbol in STOCK_BIRTHS:
        d, note, tz = STOCK_BIRTHS[symbol]
        src = "known launch/listing date"
    else:
        d, note, tz = first_date, "first trading date in the dataset", "America/New_York"
        src = "first trading date in the dataset"
    utc, *_ = local_to_utc(d, "12:00", tz)
    jd = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60)
    pos = sky_positions(jd, ayanamsa, node)["positions"]
    return {"date": d, "note": note, "source": src, "positions": pos}


ASPECTS = [("conjunction", 0, 8), ("opposition", 180, 8), ("trine", 120, 7), ("square", 90, 6), ("sextile", 60, 5)]
WEIGHT = {"Sun": 1.2, "Moon": 1.0, "Jupiter": 1.3, "Venus": 1.1, "Mercury": 0.9, "Saturn": 1.0,
          "Mars": 0.9, "Rahu": 0.8, "Ketu": 0.6, "Lagna": 1.3}


def synastry(symbol: str, first_date: str, positions: Dict, lag: int, ayanamsa: str, node: str) -> Dict:
    sc = _stock_chart(symbol, first_date, ayanamsa, node)
    sp = sc["positions"]
    contacts = []
    for a, pa in sp.items():
        if a == "Ketu":
            continue
        for b, pb in positions.items():
            if b == "Ketu":
                continue
            sep = abs((pa["longitude"] - pb["longitude"] + 180) % 360 - 180)
            for name, ang, orb in ASPECTS:
                if abs(sep - ang) <= orb:
                    harmonious = name in ("trine", "sextile") or (name == "conjunction" and (a in BENEFIC or b in BENEFIC)
                                                                  and not {a, b} & {"Saturn", "Rahu", "Mars"})
                    hard = name in ("square", "opposition") or (name == "conjunction" and {a, b} & {"Saturn", "Rahu", "Mars"})
                    w = WEIGHT.get(a, 0.8) * WEIGHT.get(b, 0.8) * (1 - abs(sep - ang) / (orb + 1))
                    pts = 6 * w if harmonious else -5 * w if hard else 1.5 * w
                    contacts.append({"stock": a, "native": b, "aspect": name, "orb": _sf(abs(sep - ang), 1),
                                     "points": _sf(pts, 1),
                                     "tone": "supportive" if pts > 0.5 else "challenging" if pts < -0.5 else "neutral",
                                     "meaning": (f"Stock's {a} {name} your {b}: "
                                                 + (f"{LORD_THEMES.get(a, 'its themes').split(';')[0].split(',')[0]} themes flow easily into your "
                                                    f"{b} — easier to hold through noise." if pts > 0.5 else
                                                    f"friction between the stock's {a} and your {b} — expect to second-guess entries; use rules."
                                                    if pts < -0.5 else "a mild link."))})
                    break
    # house placement of the stock's Sun / Moon / Jupiter in the native's chart
    house_pts = []
    for g in ("Sun", "Moon", "Jupiter"):
        h = (sp[g]["sign_number"] - lag) % 12 + 1
        p = 4 if h in (2, 5, 9, 11) else 2 if h in (1, 4, 7, 10) else -3 if h in (6, 8, 12) else 0
        house_pts.append({"stock": g, "house": h, "points": p,
                          "meaning": f"Stock's {g} falls in your house {h} — "
                                     + ("a money house: this instrument naturally plugs into your gains." if p >= 4 else
                                        "an angular house: visible, active relationship." if p == 2 else
                                        "a dusthana (6/8/12): gains tend to leak or come with stress." if p < 0 else
                                        "a neutral house.")})
    raw = sum(c["points"] for c in contacts) + sum(h["points"] for h in house_pts)
    score = int(max(5, min(95, round(50 + raw * 1.5))))
    contacts.sort(key=lambda c: -abs(c["points"] or 0))
    sup = [c for c in contacts if c["tone"] == "supportive"]
    ch = [c for c in contacts if c["tone"] == "challenging"]
    plain = (f"Using the {sc['source']} ({sc['date']}, {sc['note']}), the stock's chart has {len(sup)} supportive and "
             f"{len(ch)} challenging contacts with yours → affinity {score}/100 "
             + ("(natural fit)." if score >= 62 else "(neutral — rely on data, not affinity)." if score >= 42 else
                "(friction — keep this a smaller, rules-only position).")
             + (f" Strongest link: {contacts[0]['meaning']}" if contacts else ""))
    return {"stock_birth": {"date": sc["date"], "note": sc["note"], "source": sc["source"],
                            "positions": {k: {"sign": v["sign"], "degree": _sf(v["degree_within_sign"], 2)}
                                          for k, v in sp.items()}},
            "contacts": contacts[:14], "house_overlay": house_pts, "score": score, "plain": plain,
            "note": "Noon local time is assumed for the stock chart (no Lagna); the Moon may be ±7° off."}


# ───────────────────────── 4. verdict ─────────────────────────
def verdict(perf: Dict, trans: Dict, syn: Dict, dasha, now: datetime, symbol_name: str) -> Dict:
    cur = dasha.trading_now(now)
    ad_lord = cur["antardasha"]["lord"] if cur.get("antardasha") else None
    base = (perf.get("baseline") or {}).get("ann_return") or 0.0
    ad_row = next((r for r in perf.get("ad_by_lord", []) if r["lord"] == ad_lord), None)
    period_score = 50.0
    if ad_row and ad_row["ann_return"] is not None:
        shrink = ad_row["periods"] / (ad_row["periods"] + 1.0)  # few periods → pull toward neutral
        period_score = max(5, min(95, 50 + (ad_row["ann_return"] - base) * 100 * shrink))
    edge = trans.get("active_edge_pct") or 0.0
    trans_score = max(5, min(95, 50 + edge * 12))
    score = round(0.35 * period_score + 0.35 * trans_score + 0.30 * syn["score"])
    tone = "favourable" if score >= 60 else "neutral" if score >= 45 else "unfavourable"
    size = {"favourable": "full planned size (e.g. up to 6–8% of capital per position)",
            "neutral": "half size (≈3–4% of capital), scale in over 2–3 tranches",
            "unfavourable": "quarter size (≤2%) or paper-trade only until conditions improve"}[tone]
    good_up = [r for r in trans["upcoming"] if r["verdict"] == "better"] + \
              [r for r in trans["upcoming"] if (r["edge_pct"] or 0) > 0.3 and r["verdict"] != "better"]
    bad_now = [r for r in trans["active_now"] if (r["edge_pct"] or 0) < -0.3]
    windows = [{"label": r["label"], "from": r["window_90d"]["from"], "to": r["window_90d"]["to"],
                "edge_pct": r["edge_pct"], "kind": "favourable"} for r in good_up[:3]]
    windows += [{"label": r["label"], "from": r["window_90d"]["from"], "to": r["window_90d"]["to"],
                 "edge_pct": r["edge_pct"], "kind": "caution"} for r in bad_now[:2]]
    actions = []
    if tone == "favourable":
        actions.append(f"Entries: accumulate {symbol_name} on pullbacks (e.g. to the 20/50-day average) rather than chasing.")
    elif tone == "neutral":
        actions.append(f"Entries: only on confirmed set-ups in {symbol_name}; split buys into 2–3 tranches a week or more apart.")
    else:
        actions.append(f"Entries: wait — let the current {ad_lord} sub-period/transits pass or demand extra technical confirmation.")
    actions.append(f"Sizing: {size}; always pre-set a stop (e.g. 1.5–2× ATR).")
    if windows:
        w = windows[0]
        actions.append(f"Timing: {w['kind']} window {w['from']} → {w['to']} ({w['label']}, historical edge {w['edge_pct']:+.2f} pts/month).")
    if cur.get("pratyantardasha"):
        actions.append(f"This fortnight ({cur['pratyantardasha']['lord']} pratyantardasha until {cur['pratyantardasha']['end']}): "
                       f"{cur['pratyantardasha']['meaning']}")
    plain = (f"Right now {symbol_name} looks {tone} for you (fit {score}/100): dasha-period history {round(period_score)}/100, "
             f"active transits {round(trans_score)}/100, chart affinity {syn['score']}/100.")
    return {"score": score, "tone": tone, "components": {"dasha_history": round(period_score),
                                                          "transits": round(trans_score), "synastry": syn["score"]},
            "actions": actions, "windows": windows, "plain": plain,
            "disclaimer": "Educational, not financial advice. Historical coincidences do not guarantee future returns."}


def stock_kundli(close: pd.Series, symbol: str, symbol_name: str, chart: Dict,
                 demo: bool = False, now: Optional[datetime] = None) -> Dict:
    now = now or datetime.utcnow()
    close = close[close > 0].dropna()
    if getattr(close.index, "tz", None) is not None:
        close.index = close.index.tz_localize(None)
    if len(close) < 200:
        return {"success": False, "error": f"Not enough price history for {symbol} ({len(close)} rows)."}
    positions, lag = chart["positions"], chart["lagna_sign"]
    st = chart["settings"]
    dasha = chart["dasha"]
    perf = dasha_performance(close, dasha, now)
    trans = transit_study(close, positions, lag, st["ayanamsa"], st["node"], now)
    syn = synastry(symbol, close.index[0].strftime("%Y-%m-%d"), positions, lag, st["ayanamsa"], st["node"])
    ver = verdict(perf, trans, syn, dasha, now, symbol_name)
    return {"success": True, "symbol": symbol, "symbol_name": symbol_name,
            "history": {"start": close.index[0].strftime("%Y-%m-%d"), "end": close.index[-1].strftime("%Y-%m-%d"),
                        "days": int(len(close))},
            "data_note": ("Prices are SYNTHETIC demo data (no live market feed in this environment) — the method is real, "
                          "the numbers are not." if demo else "Live/cached market history."),
            "native": chart["birth"]["name"],
            "dasha_now": dasha.trading_now(now),
            "periods": perf, "transits": trans, "synastry": syn, "verdict": ver}
