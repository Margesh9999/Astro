"""
Sky Events x Your Stock — event studies (v1.3)
==============================================
For every classical event in the next N days (lunations, eclipses, stations,
sidereal ingresses, aspects, combustion) we look up every PAST occurrence of
the same event type in the full sky table (1925 -> today) and measure how the
selected stock behaved afterwards:

  avg 1 / 5 / 20-session forward return vs the stock's normal k-day return,
  hit rate, t-statistic, first-week volatility vs the 60 sessions before,
  and the last few occurrences.

The result is turned into a symbol-specific, plain-English meaning + action,
next to the classical astrological reading and the sector rulers it touches.
Event dates over the full history are detected once (SkyTable.events) and the
per-symbol studies are cached until the price history changes.
Educational only — history is not a forecast.
"""
from __future__ import annotations

import math
import threading
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.services.cycles_sky import SIGNS, SKY
from app.services.cycles_stats import PricePanel, fmt_date, fnum

HORIZONS = (1, 5, 20)
DEDUPE_DAYS = 20  # retrograde loops make some aspects perfect 3x within weeks
# ~25 event types x 3 horizons are tested per symbol: |t| >= 3 keeps the family-wise
# false-positive rate near 5% (Bonferroni); 1.96 <= |t| < 3 is only a "weak hint"
T_SIG = 3.0

PLANET_SECTORS: Dict[str, List[str]] = {
    "Sun": ["PSU / government", "power & energy", "gold"],
    "Moon": ["FMCG & food", "liquidity / retail sentiment", "silver"],
    "Mercury": ["IT / software", "telecom", "media", "brokers & trading"],
    "Venus": ["luxury", "FMCG & cosmetics", "autos", "hospitality & entertainment"],
    "Mars": ["metals & steel", "defence", "real estate", "engineering"],
    "Jupiter": ["banking", "finance & insurance", "education", "gold"],
    "Saturn": ["infrastructure", "oil & gas", "mining", "heavy industry"],
    "Rahu": ["tech disruptors", "crypto", "aviation & imports", "chemicals"],
    "Ketu": ["pharma", "research", "alternative assets"],
}
SECTOR_PLANETS: Dict[str, List[str]] = {
    "Technology": ["Mercury", "Rahu"], "IT": ["Mercury"], "India Tech": ["Mercury"],
    "Internet": ["Mercury", "Rahu"], "Communication": ["Mercury"], "Media": ["Mercury", "Venus"],
    "Financials": ["Jupiter"], "India Financials": ["Jupiter"], "Payments": ["Jupiter", "Mercury"],
    "Exchange": ["Jupiter", "Mercury"], "Consumer Disc.": ["Venus"], "Automobile": ["Venus", "Mars"],
    "Retail": ["Venus", "Moon"], "Travel": ["Venus", "Rahu"], "Consumer Staples": ["Moon", "Venus"],
    "Materials": ["Mars", "Saturn"], "Industrials": ["Saturn", "Mars"], "Defence": ["Mars"],
    "Real Estate": ["Mars", "Saturn"], "Energy": ["Saturn", "Sun"], "Utilities": ["Sun", "Saturn"],
    "Healthcare": ["Sun", "Jupiter", "Ketu"], "Commodities": ["Saturn", "Mars"],
    "Layer 1": ["Rahu", "Mercury"], "Majors": ["Rahu", "Mercury"], "Meme": ["Rahu"], "Oracle": ["Rahu", "Mercury"],
    "Bonds": ["Jupiter", "Saturn"], "Cash+": ["Jupiter"], "Volatility": ["Moon", "Mars", "Rahu"],
    "Conglomerate": ["Jupiter", "Saturn"],
}
BROAD_HINTS = ("Index", "Large Cap", "Broad", "Blue Chip", "Small Cap", "Mid Cap", "International",
               "Emerging", "Balanced", "US Growth", "Index ETF", "Sector", "Thematic")

EXALT = {"Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn", "Mercury": "Virgo", "Jupiter": "Cancer",
         "Venus": "Pisces", "Saturn": "Libra", "Rahu": "Taurus"}
OWN = {"Sun": ["Leo"], "Moon": ["Cancer"], "Mars": ["Aries", "Scorpio"], "Mercury": ["Gemini", "Virgo"],
       "Jupiter": ["Sagittarius", "Pisces"], "Venus": ["Taurus", "Libra"], "Saturn": ["Capricorn", "Aquarius"],
       "Rahu": ["Aquarius"]}

RETRO_LORE = {
    "Mercury": "Mercury retrograde — contracts, communication and tech glitches; markets often re-test old levels and reverse recent moves",
    "Venus": "Venus retrograde — values and luxury spending are reassessed; consumer and currency themes wobble",
    "Mars": "Mars retrograde — energy turns inward; momentum stalls, commodity and defence stories reverse",
    "Jupiter": "Jupiter retrograde — optimism and credit expansion pause; financials consolidate",
    "Saturn": "Saturn retrograde — old structural problems (debt, regulation) resurface for review",
}
DIRECT_LORE = {
    "Mercury": "Mercury turns direct — delayed decisions get made; the market picks a direction again within days",
    "Venus": "Venus turns direct — consumer confidence and risk appetite slowly return",
    "Mars": "Mars turns direct — drive returns; breakouts become more trustworthy",
    "Jupiter": "Jupiter turns direct — growth and lending sentiment re-expands",
    "Saturn": "Saturn turns direct — structural pressure moves forward; discipline is rewarded",
}
ASPECT_LORE = {
    "conjunction": "energies merge and a new cycle between the two planets begins",
    "opposition": "the two forces pull apart — culmination, tension and reversal risk",
    "square": "friction between the two significations — choppy, decision-forcing tape",
    "trine": "easy flow between the two significations — supports continuation",
}
PLANET_THEME = {
    "Sun": "authority / government", "Mercury": "news, trade & tech", "Venus": "consumption & pleasure",
    "Mars": "aggression & energy", "Jupiter": "growth & credit", "Saturn": "restriction & structure",
    "Rahu": "speculation & disruption", "Ketu": "detachment & sudden breaks", "Moon": "crowd mood",
}


def _display_name(key: str) -> str:
    fam = key.split(":")[0]
    parts = key.split(":")
    if fam == "lunation":
        return {"new": "New Moons", "full": "Full Moons", "first_quarter": "First-Quarter Moons",
                "last_quarter": "Last-Quarter Moons"}[parts[1]]
    if fam == "eclipse":
        return {"solar": "solar eclipses", "lunar": "lunar eclipses",
                "lunar_penumbral": "penumbral lunar eclipses"}[parts[1]]
    if fam == "station":
        return f"{parts[1]} {'retrograde' if parts[2] == 'retro' else 'direct'} stations"
    if fam == "ingress":
        return f"{parts[1]} ingresses into {parts[2]}" if len(parts) > 2 else f"{parts[1]} sign changes (any sign)"
    if fam == "aspect":
        return f"{parts[1].replace('-', '–')} {parts[2]}s"
    if fam == "combust":
        return f"{parts[1]} combustions"
    return key


class EventStudyEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._occ: Optional[Dict[str, np.ndarray]] = None
        self._cache: Dict[Tuple[str, str, str], Dict] = {}

    # occurrences by key (+ generic ingress keys), deduped
    def occurrences(self) -> Dict[str, np.ndarray]:
        if self._occ is not None:
            return self._occ
        with self._lock:
            if self._occ is None:
                by: Dict[str, List[int]] = {}
                for e in SKY.events():
                    by.setdefault(e["key"], []).append(e["i"])
                    if e["family"] == "ingress":
                        by.setdefault(f"ingress:{e['planet']}", []).append(e["i"])
                occ = {}
                for k, v in by.items():
                    v = sorted(v)
                    keep, last = [], -10 ** 9
                    for i in v:
                        if i - last > DEDUPE_DAYS:
                            keep.append(i)
                            last = i
                    occ[k] = np.array(keep, dtype=int)
                self._occ = occ
        return self._occ

    def study(self, pp: PricePanel, key: str, before_idx: int) -> Dict:
        occ = self.occurrences().get(key, np.array([], dtype=int))
        occ = occ[occ < before_idx]
        rows = np.array([pp.first_on_or_after(i) for i in occ], dtype=int) if len(occ) else np.array([], dtype=int)
        # need a 60-session lookback for the volatility baseline and the event session itself
        valid = (rows >= 61) & (rows < pp.n)
        # drop occurrences that fall in a long market closure (session > 4 days after the event)
        if len(rows):
            valid &= np.array([(pp.sky_i[r] - i) <= 4 if r < pp.n else False for r, i in zip(rows, occ)])
        rows, occ = rows[valid], occ[valid]
        res: Dict = {"key": key, "label": _display_name(key), "n": int(len(rows))}
        if len(rows) == 0:
            res.update({"verdict": "too few", "h": {}})
            return res
        h = {}
        max_t = 0.0
        for k in HORIZONS:
            fk = pp.fwd(k)
            base = fk[~np.isnan(fk)]
            ev = fk[rows]
            ev = ev[~np.isnan(ev)]
            if len(ev) == 0 or len(base) < 50:
                continue
            bm, bs = float(np.mean(base)), float(np.std(base))
            m = float(np.mean(ev))
            t = (m - bm) / (bs / math.sqrt(len(ev))) if bs > 0 else 0.0
            if len(ev) >= 8:
                max_t = max(max_t, abs(t))
            h[str(k)] = {"n": int(len(ev)), "mean_pct": fnum(m * 100, 3), "base_pct": fnum(bm * 100, 3),
                         "excess_pct": fnum((m - bm) * 100, 3), "hit_pct": fnum(np.mean(ev > 0) * 100, 1),
                         "base_hit_pct": fnum(np.mean(base > 0) * 100, 1), "t": fnum(t, 2),
                         "abs_pct": fnum(np.mean(np.abs(ev)) * 100, 3),
                         "base_abs_pct": fnum(np.mean(np.abs(base)) * 100, 3)}
        # first-week volatility vs the 60 sessions before, relative to the same ratio on ALL days
        # (vol clusters, so the raw ratio is biased; comparing with the unconditional ratio removes that)
        all_lr = pp.vol_log_ratios()
        ev_lr = all_lr[rows]
        ev_lr = ev_lr[~np.isnan(ev_lr)]
        base_lr = all_lr[~np.isnan(all_lr)]
        if len(ev_lr) > 2 and len(base_lr) > 50 and np.std(base_lr) > 0:
            vr = float(np.exp(np.mean(ev_lr) - np.mean(base_lr)))
            vt = float((np.mean(ev_lr) - np.mean(base_lr)) / (np.std(base_lr) / math.sqrt(len(ev_lr))))
        else:
            vr, vt = 1.0, 0.0
        n = len(rows)
        res.update({
            "h": h, "vol_ratio": fnum(vr, 2), "vol_t": fnum(vt, 2),
            "verdict": ("too few" if n < 8 else "significant" if max_t >= T_SIG else "weak" if max_t >= 1.96 else "noise"),
            "vol_verdict": ("too few" if n < 8 else "significant" if abs(vt) >= T_SIG else "weak" if abs(vt) >= 1.96 else "noise"),
            "first": SKY.date_of(int(occ[0])), "last": SKY.date_of(int(occ[-1])),
            "recent": [{"date": SKY.date_of(int(i)),
                        "r20_pct": fnum((pp.close[min(r - 1 + 20, pp.n - 1)] / pp.close[r - 1] - 1) * 100, 2)}
                       for i, r in list(zip(occ, rows))[-3:]][::-1],
        })
        return res


ENGINE = EventStudyEngine()


# ---------------------------------------------------------------------------
# symbol context
# ---------------------------------------------------------------------------
def symbol_planets(sector: str, name: str) -> Tuple[List[str], bool]:
    nm = (name or "").lower()
    pl: List[str] = []
    if "gold" in nm:
        pl += ["Sun", "Jupiter"]
    if "silver" in nm:
        pl += ["Moon"]
    if "oil" in nm or "crude" in nm:
        pl += ["Saturn"]
    if "bitcoin" in nm or "crypto" in nm or "ethereum" in nm:
        pl += ["Rahu"]
    pl += SECTOR_PLANETS.get(sector, [])
    broad = (not pl) and (sector in ("Index", "N/A", "") or any(h in sector for h in BROAD_HINTS))
    return list(dict.fromkeys(pl)), broad


def stock_context(pp: PricePanel) -> Dict:
    c = pp.close
    r = pp.ret[~np.isnan(pp.ret)]
    chg = float(c[-1] / c[-64] - 1) if pp.n > 64 else 0.0
    trend = "up" if chg > 0.02 else ("down" if chg < -0.02 else "sideways")
    v21 = float(np.std(r[-21:]) * math.sqrt(252)) if len(r) > 21 else 0.0
    v1y = float(np.std(r[-252:]) * math.sqrt(252)) if len(r) > 60 else v21
    vol_state = "elevated" if v21 > v1y * 1.25 else ("calm" if v21 < v1y * 0.8 else "normal")
    return {"trend": trend, "chg_3m_pct": fnum(chg * 100, 2), "vol21_pct": fnum(v21 * 100, 1),
            "vol1y_pct": fnum(v1y * 100, 1), "vol_state": vol_state, "spot": fnum(c[-1], 2)}


# ---------------------------------------------------------------------------
# classical meaning
# ---------------------------------------------------------------------------
def classical(ev: Dict) -> str:
    fam = ev["family"]
    k = ev["key"].split(":")
    if fam == "lunation":
        return {"new": "Amavasya — the lunar cycle resets; classically a low-energy, low-conviction session that seeds the next fortnight's trend",
                "full": "Purnima — emotions and sentiment peak; classically a culmination point where crowded trades reverse",
                "first_quarter": "First quarter — the waxing Moon's first test; trends started at the New Moon are confirmed or fail",
                "last_quarter": "Last quarter — the waning Moon's clean-up phase; weak hands exit before the next New Moon"}[k[1]]
    if fam == "eclipse":
        return ("Grahan — Rahu/Ketu 'swallow' a luminary; classically the most disruptive lunation of the year, "
                "with effects said to unfold over the following weeks; traders avoid fresh commitments around it")
    if fam == "station":
        return (RETRO_LORE if k[2] == "retro" else DIRECT_LORE).get(k[1], "planetary station")
    if fam == "ingress":
        p, sign = k[1], k[2]
        dig = ("exalted (strongest)" if EXALT.get(p) == sign else
               "debilitated (weakest)" if EXALT.get(p) and SIGNS[(SIGNS.index(EXALT[p]) + 6) % 12] == sign else
               "in its own sign (comfortable)" if sign in OWN.get(p, []) else "in a neutral sign")
        if p == "Sun":
            return (f"Sankranti — the Sun enters {sign}; the solar month changes and with it the seasonal "
                    f"theme. The Sun is {dig} here.")
        return (f"{p} ({PLANET_THEME.get(p, '')}) moves into {sign} and is {dig} there — the market's "
                f"{PLANET_THEME.get(p, 'theme')} narrative shifts for the length of the transit")
    if fam == "aspect":
        a, b = k[1].split("-")
        return (f"{a} ({PLANET_THEME.get(a, '')}) and {b} ({PLANET_THEME.get(b, '')}): "
                f"{ASPECT_LORE.get(k[2], 'aspect')}")
    if fam == "combustion":
        p = k[1]
        return (f"{p} is 'burnt' by the Sun (asta) — its significations ({PLANET_THEME.get(p, '')}) lose "
                f"strength for ~{ev.get('days', 0)} days; related news gets overshadowed")
    return "notable sky event"


# ---------------------------------------------------------------------------
# dynamic meaning + action
# ---------------------------------------------------------------------------
def meaning_and_action(ev: Dict, st: Dict, name: str, ctx: Dict, touched: bool, broad: bool) -> Tuple[str, str, float]:
    """Returns (meaning, action, tilt) where tilt is -1..+1 (bearish..bullish)."""
    d0 = date.fromisoformat(ev["date"])
    w1 = fmt_date((d0 + timedelta(days=7)).isoformat())
    w4 = fmt_date((d0 + timedelta(days=28)).isoformat())
    dd = fmt_date(ev["date"])
    n = st.get("n", 0)
    h = st.get("h", {})
    if n < 8 or "20" not in h:
        meaning = (f"Only {n} past occurrence{'s' if n != 1 else ''} of {st['label']} inside {name}'s price history — "
                   f"too few to measure an effect.")
        action = ("No data edge: don't trade the event itself. "
                  + ("Keep following the uptrend with a trailing stop." if ctx["trend"] == "up" else
                     "Respect the downtrend — no bottom-fishing on the date alone." if ctx["trend"] == "down" else
                     "Range rules apply: buy near support, trim near resistance."))
        return meaning, action, 0.0
    h20, h5 = h["20"], h.get("5", h["20"])
    vr = st.get("vol_ratio", 1.0)
    meaning = (f"Last {n} {st['label']}: {name} averaged {h20['mean_pct']:+.1f}% over the next 20 sessions "
               f"(normal {h20['base_pct']:+.1f}%), up {h20['hit_pct']:.0f}% of the time vs {h20['base_hit_pct']:.0f}% normally; "
               f"first-week volatility ran {vr:.2f}× its normal pace.")
    v = st["verdict"]
    meaning += {"significant": f" The return difference is statistically meaningful (t {h20['t']:+.1f}).",
                "weak": f" Only a weak hint (best t {max(abs(x['t']) for x in h.values()):.1f}) — could be chance.",
                "noise": " Statistically this is noise — the stock behaves about normally around this event."}[v]
    if st.get("vol_verdict") == "significant":
        meaning += f" The volatility change IS significant (t {st['vol_t']:+.1f})."
    tilt = 0.0
    ex20, ex5 = h20["excess_pct"], h5["excess_pct"]
    parts: List[str] = []
    if v in ("significant", "weak"):
        tilt = max(-1.0, min(1.0, ex20 / 2.0)) * (1.0 if v == "significant" else 0.5)
        if ex20 < 0:
            parts.append(f"Historically a headwind — consider lighter positions from {dd} to {w4}"
                         + ("; buy protective puts or tighten stops if holding" if ctx["trend"] != "down" else
                            "; it can extend the current downtrend, so don't catch the knife"))
        else:
            parts.append(f"Historically a tailwind — {'hold winners and add on dips' if ctx['trend'] != 'down' else 'watch for a bounce'} "
                         f"from {dd} to {w4}")
    if vr >= 1.15 and st.get("vol_verdict") in ("significant", "weak"):
        parts.append(f"expect bigger swings from {dd} to {w1}: size down ~{min(50, int((vr - 1) * 100))}% and widen stops"
                     + (" — volatility is already elevated" if ctx["vol_state"] == "elevated" else ""))
    elif vr <= 0.88 and st.get("vol_verdict") in ("significant", "weak"):
        parts.append(f"moves tend to be quieter than usual into {w1} — premium selling (covered calls) fits better than breakout buys")
    if not parts:
        base = ("No reliable edge — don't trade the date itself; "
                + ("stay with the uptrend and trail stops." if ctx["trend"] == "up" else
                   "the downtrend is the bigger force; keep rallies for trimming." if ctx["trend"] == "down" else
                   "keep trading the range with small size."))
        parts.append(base)
    action = "; ".join(p.rstrip(".") for p in parts)
    action = action[0].upper() + action[1:] + "."
    if touched:
        action += f" Sector rulers of {name} are directly involved, so treat this event as higher-priority than usual."
    elif broad and ev["importance"] == "High":
        action += " As a broad index it feels this mainly through sentiment and its sector weights."
    return meaning, action, tilt


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------
def events_with_study(df: pd.DataFrame, symbol: str, name: str, sector: str, days: int = 45) -> Dict:
    pp = PricePanel(df)
    if pp.n < 300:
        return {"success": False, "error": "not enough price history for an event study"}
    ckey = (symbol, str(pp.dates[-1]), str(days))
    if ckey in ENGINE._cache:
        return ENGINE._cache[ckey]
    t_i = SKY.today_idx()
    upcoming = [e for e in SKY.events() if t_i <= e["i"] < t_i + days]
    ctx = stock_context(pp)
    sym_pl, broad = symbol_planets(sector, name)
    occ = ENGINE.occurrences()
    studies: Dict[str, Dict] = {}
    out_events = []
    for e in upcoming:
        key = e["key"]
        if e["family"] == "ingress":
            specific = occ.get(key, np.array([]))
            if (specific < t_i).sum() < 12:
                key = f"ingress:{e['planet']}"
        if key not in studies:
            studies[key] = ENGINE.study(pp, key, t_i)
        st = studies[key]
        planets = list(e["planets"])
        if "Ketu" in e["title"] and "Ketu" not in planets:
            planets.append("Ketu")
        rulers = [{"planet": p, "sectors": PLANET_SECTORS.get(p, [])}
                  for p in planets if p in PLANET_SECTORS and not (e["family"] == "lunation" and p == "Sun")]
        touched_by = [p for p in planets if p in sym_pl]
        touched = bool(touched_by)
        meaning, action, tilt = meaning_and_action(e, st, name, ctx, touched, broad)
        h5 = st.get("h", {}).get("5", {})
        out_events.append({
            "date": e["date"], "title": e["title"], "family": e["family"], "key": e["key"],
            "study_key": key, "importance": e["importance"], "planets": planets,
            "classical": classical(e), "meaning": meaning, "action": action, "tilt": fnum(tilt, 2),
            "study": st, "expected_5d_pct": h5.get("excess_pct", 0.0),
            "sector_rulers": rulers, "touches_stock": touched, "touched_by": touched_by,
        })
    hi = [x for x in out_events if x["importance"] == "High"]
    notable = sorted([x for x in out_events if x["study"].get("verdict") in ("significant", "weak")],
                     key=lambda x: -abs(x["study"]["h"].get("20", {}).get("t", 0)))
    if notable:
        top = notable[0]
        summary = (f"{len(out_events)} sky events in the next {days} days ({len(hi)} high-importance). "
                   f"The one with the clearest history for {name}: {top['title']} on {fmt_date(top['date'])} — "
                   f"{top['action']}")
    else:
        summary = (f"{len(out_events)} sky events in the next {days} days ({len(hi)} high-importance), but none has a "
                   f"statistically reliable track record for {name}. Treat them as a calendar of possible "
                   f"turbulence; position sizing and the {ctx['trend']} trend matter more.")
    pack = {
        "success": True, "symbol": symbol, "symbol_name": name, "sector": sector,
        "sector_planets": sym_pl, "broad_market": broad, "context": ctx, "days": days,
        "history_start": pp.start, "history_days": int(pp.n),
        "events": out_events, "count": len(out_events), "summary": summary,
        "planets": sorted({p for x in out_events for p in x["planets"]}),
        "method": ("For each event type we find every past occurrence since 1925 (repeats within 20 days merged), "
                   "start on the first session on/after the date and compare the stock's 1/5/20-session returns with its "
                   "normal k-session return. t = excess ÷ standard error; 'significant' needs |t| ≥ 3 (multiple-comparison hurdle) and ≥ 8 cases. "
                   "Volatility ratio = first-week |daily move| ÷ the 60 sessions before, relative to the same ratio on all days (1.0× = normal)."),
    }
    if len(ENGINE._cache) > 64:
        ENGINE._cache.clear()
    ENGINE._cache[ckey] = pack
    return pack
