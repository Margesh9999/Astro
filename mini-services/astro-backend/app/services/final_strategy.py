"""
Final Strategy aggregator (v1.3).

Takes every individual signal the product computes — quant regime, technical
consensus, ML model-zoo, Suri composite + timing alerts, sky events, the
TradingAgents decision, natal strengths, current dasha and today's transits —
and turns them into ONE plan: a weighted signal scoreboard, natal-vs-today
planetary comparison, 30 / 60 / 90 / 365-day playbooks with entries, stops,
targets, key dates and sizing, and an illustrative weekly-income plan.

Pure functions over already-gathered inputs (the route does the gathering, each
input wrapped in try/except). Educational only — not financial advice; every
income figure is illustrative and never guaranteed.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import swisseph as swe

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
SWE_IDS = {"Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
           "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}
ASPECTS = [(0, "conjunction", 8.0), (180, "opposition", 6.0), (90, "square", 5.0), (120, "trine", 5.0)]
BENEFIC_T = ("Jupiter", "Venus", "Mercury", "Moon")
# classical gochar: favourable houses counted from the natal Moon
GOCHAR_GOOD = {"Sun": {3, 6, 10, 11}, "Moon": {1, 3, 6, 7, 10, 11}, "Mars": {3, 6, 11},
               "Mercury": {2, 4, 6, 8, 10, 11}, "Jupiter": {2, 5, 7, 9, 11},
               "Venus": {1, 2, 3, 4, 5, 8, 9, 11, 12}, "Saturn": {3, 6, 11},
               "Rahu": {3, 6, 11}, "Ketu": {3, 6, 11}}

HORIZONS = [(30, "Next 30 days"), (60, "Days 31–60"), (90, "Days 61–90"), (365, "Months 4–12")]
# per-horizon weight multipliers: short horizons trust timing/technicals, long ones regime/dasha
H_MULT = {
    30: {"technical": 1.4, "suri": 1.3, "sky": 1.3, "agents": 1.2, "ml": 1.0, "quant": 0.6, "natal": 0.5, "dasha": 0.7, "transits": 1.2},
    60: {"technical": 1.1, "suri": 1.0, "sky": 1.0, "agents": 1.1, "ml": 1.0, "quant": 0.9, "natal": 0.7, "dasha": 0.9, "transits": 1.0},
    90: {"technical": 0.9, "suri": 0.8, "sky": 0.8, "agents": 1.0, "ml": 0.9, "quant": 1.1, "natal": 0.9, "dasha": 1.1, "transits": 0.8},
    365: {"technical": 0.5, "suri": 0.4, "sky": 0.4, "agents": 0.8, "ml": 0.6, "quant": 1.5, "natal": 1.2, "dasha": 1.5, "transits": 0.5},
}


def _n(x, d: float = 0.0) -> float:
    try:
        v = float(x)
        return d if (math.isnan(v) or math.isinf(v)) else v
    except (TypeError, ValueError):
        return d


def _clip(x: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _sig(score: float, band: float = 10.0) -> str:
    return "bullish" if score >= band else ("bearish" if score <= -band else "neutral")


def _fmt(x: float) -> str:
    x = _n(x)
    return f"{x:,.2f}" if abs(x) < 1000 else f"{x:,.0f}"


def _sep(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


# =============================================================================
# 1. natal vs today
# =============================================================================

def today_positions(vedic, when: Optional[datetime] = None) -> Dict[str, Dict]:
    now = when or datetime.utcnow()
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute / 60.0)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    out: Dict[str, Dict] = {}
    for g, pid in SWE_IDS.items():
        d = vedic.calculate_planet_position_vedic(pid, jd)
        out[g] = {"longitude": _n(d["longitude"]), "sign_number": int(d["sign_number"]),
                  "sign": d["sign"], "degree": round(_n(d["degree_within_sign"]), 2),
                  "nakshatra": d.get("nakshatra"), "pada": d.get("pada"),
                  "retrograde": bool(d.get("is_retrograde")) and g not in ("Rahu",)}
    k = (out["Rahu"]["longitude"] + 180) % 360
    nak = vedic.calculate_nakshatra(k)
    out["Rahu"]["retrograde"] = True
    out["Ketu"] = {"longitude": k, "sign_number": int(k // 30), "sign": SIGNS[int(k // 30)],
                   "degree": round(k % 30, 2), "nakshatra": nak.get("nakshatra"), "pada": nak.get("pada"),
                   "retrograde": True}
    return out


def natal_vs_today(positions: Dict, strengths: Dict, vedic) -> Dict:
    today = today_positions(vedic)
    lagna = int(positions["Lagna"]["sign_number"])
    moon_sign = int(positions["Moon"]["sign_number"])
    scores = (strengths or {}).get("scores", {})
    rows = []
    for g in GRAHAS:
        n = positions.get(g) or {}
        t = today.get(g) or {}
        if not n or not t:
            continue
        t_house = (t["sign_number"] - lagna) % 12 + 1
        from_moon = (t["sign_number"] - moon_sign) % 12 + 1
        good = from_moon in GOCHAR_GOOD.get(g, set())
        rows.append({
            "graha": g,
            "natal_sign": n.get("sign"), "natal_degree": round(_n(n.get("degree_within_sign")), 2),
            "natal_house": n.get("house"), "natal_nakshatra": n.get("nakshatra"),
            "natal_dignity": n.get("dignity"), "natal_retro": bool(n.get("is_retrograde")),
            "strength": scores.get(g),
            "today_sign": t["sign"], "today_degree": t["degree"], "today_house": t_house,
            "today_nakshatra": t.get("nakshatra"), "today_retro": t["retrograde"],
            "house_from_moon": from_moon, "gochar": "favourable" if good else "challenging",
        })
    # activations: transiting graha aspects natal points (incl. Lagna)
    acts = []
    natal_pts = {g: _n(p.get("longitude")) for g, p in positions.items() if isinstance(p, dict) and "longitude" in p}
    for tg, tp in today.items():
        if tg == "Moon":  # moves 13°/day — too noisy for a strategy view
            continue
        for ng, nl in natal_pts.items():
            if tg in ("Rahu", "Ketu") and ng in ("Rahu", "Ketu"):
                continue
            sep_full = _sep(tp["longitude"], nl)
            for ang, kind, orb in ASPECTS:
                diff = abs(sep_full - ang)
                if diff <= orb:
                    tone = ("supportive" if (kind in ("trine",) or (kind == "conjunction" and tg in BENEFIC_T))
                            else "testing" if kind in ("square", "opposition") or tg in ("Saturn", "Mars", "Rahu", "Ketu")
                            else "neutral")
                    acts.append({"transit": tg, "natal": ng, "aspect": kind, "orb": round(diff, 1), "tone": tone,
                                 "meaning": _activation_meaning(tg, ng, kind, tone)})
                    break
    acts.sort(key=lambda a: (a["orb"], a["transit"]))
    # special flags
    flags = []
    sat_from_moon = (today["Saturn"]["sign_number"] - moon_sign) % 12 + 1
    if sat_from_moon in (12, 1, 2):
        phase = {12: "rising", 1: "peak", 2: "setting"}[sat_from_moon]
        flags.append({"flag": "Sade Sati", "tone": "testing",
                      "text": f"Saturn transits house {sat_from_moon} from your Moon — Sade Sati ({phase} phase): "
                              "favour capital preservation, smaller size and defined-risk trades."})
    elif sat_from_moon in (4, 8):
        flags.append({"flag": "Dhaiya", "tone": "testing",
                      "text": f"Saturn transits house {sat_from_moon} from your Moon (small panoti) — avoid leverage."})
    jup_from_moon = (today["Jupiter"]["sign_number"] - moon_sign) % 12 + 1
    if jup_from_moon in GOCHAR_GOOD["Jupiter"]:
        flags.append({"flag": "Jupiter gochar", "tone": "supportive",
                      "text": f"Jupiter transits house {jup_from_moon} from your Moon — a classically favourable "
                              "period for growth and patient accumulation."})
    n_good = sum(1 for r in rows if r["gochar"] == "favourable")
    score = _clip((n_good - len(rows) / 2) * 12
                  + sum(4 if a["tone"] == "supportive" else -4 if a["tone"] == "testing" else 0 for a in acts[:8])
                  + sum(10 if f["tone"] == "supportive" else -10 for f in flags))
    return {
        "lagna_sign_number": lagna, "lagna_sign": SIGNS[lagna], "moon_sign": SIGNS[moon_sign],
        "rows": rows, "activations": acts[:12], "flags": flags,
        "natal_chart": [{"name": g, "signNumber": int(positions[g]["sign_number"]),
                         "degree": round(_n(positions[g].get("degree_within_sign")), 2),
                         "retrograde": bool(positions[g].get("is_retrograde")), "house": positions[g].get("house"),
                         "dignity": positions[g].get("dignity"), "nakshatra": positions[g].get("nakshatra"),
                         "pada": positions[g].get("pada")} for g in GRAHAS if g in positions],
        "today_chart": [{"name": g, "signNumber": today[g]["sign_number"], "degree": today[g]["degree"],
                         "retrograde": today[g]["retrograde"], "house": (today[g]["sign_number"] - lagna) % 12 + 1,
                         "nakshatra": today[g].get("nakshatra"), "pada": today[g].get("pada")} for g in GRAHAS],
        "score": round(score, 1),
        "favourable_count": n_good,
        "interpretation": (f"{n_good} of {len(rows)} grahas transit favourable houses from your Moon "
                           f"({SIGNS[moon_sign]}); {len(acts)} transit(s) currently touch natal points"
                           + (f", led by transiting {acts[0]['transit']} {acts[0]['aspect']} natal {acts[0]['natal']} "
                              f"({acts[0]['orb']}° orb)" if acts else "")
                           + ". " + (flags[0]["text"] if flags else "No Sade Sati or Saturn-dhaiya pressure right now.")),
    }


def _activation_meaning(tg: str, ng: str, kind: str, tone: str) -> str:
    verb = {"conjunction": "sits on", "opposition": "opposes", "square": "squares", "trine": "trines"}[kind]
    act = ("lean in — conditions favour acting on well-planned trades" if tone == "supportive" else
           "slow down — tighten stops and avoid impulsive size" if tone == "testing" else
           "notice it — a theme is activated, act only with confirmation")
    return f"Transiting {tg} {verb} your natal {ng}: {act}."


# =============================================================================
# 2. key dates over the next year
# =============================================================================

def slow_planet_dates(days: int = 365) -> List[Dict]:
    """Sidereal sign ingresses of Mars/Jupiter/Saturn/Rahu + Mercury/Venus/Mars/Jupiter/Saturn stations."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    jd0 = swe.julday(today.year, today.month, today.day, 12.0)
    out: List[Dict] = []
    for name in ("Mars", "Jupiter", "Saturn", "Rahu", "Mercury", "Venus"):
        pid = SWE_IDS[name]
        prev = None
        for i in range(0, days + 1):
            try:
                pos, _ = swe.calc_ut(jd0 + i, pid, flag)
            except Exception:
                break
            lon, sp = pos[0] % 360, pos[3]
            if prev is not None:
                plon, psp = prev
                if name in ("Mars", "Jupiter", "Saturn", "Rahu") and int(lon // 30) != int(plon // 30):
                    out.append({"date": (today + timedelta(days=i)).date().isoformat(), "days_ahead": i,
                                "kind": "ingress", "title": f"{name} enters {SIGNS[int(lon // 30)]}",
                                "weight": 3 if name in ("Jupiter", "Saturn") else 2,
                                "note": "slow-planet sign change — sector leadership rotates; review the plan"})
                if name != "Rahu" and psp * sp < 0:
                    turn = "retrograde" if sp < 0 else "direct"
                    out.append({"date": (today + timedelta(days=i)).date().isoformat(), "days_ahead": i,
                                "kind": "station", "title": f"{name} stations {turn}",
                                "weight": 2 if name == "Mercury" else 3 if name in ("Jupiter", "Saturn") else 2,
                                "note": "stations mark turning points — avoid fresh entries ±2 days"})
            prev = (lon, sp)
    return out


def dasha_dates(dasha, days: int = 365) -> List[Dict]:
    out: List[Dict] = []
    if dasha is None:
        return out
    now = datetime.now()
    end = now + timedelta(days=days)
    try:
        for md in dasha.tree:
            if md["end"] < now or md["start"] > end:
                continue
            if now <= md["start"] <= end:
                out.append({"date": md["start"].date().isoformat(), "days_ahead": (md["start"] - now).days,
                            "kind": "dasha", "title": f"{md['lord']} Mahadasha begins", "weight": 3,
                            "note": "major life-chapter change — rebuild the long-term plan"})
            for ad in md.get("antardashas", []):
                if now <= ad["start"] <= end:
                    out.append({"date": ad["start"].date().isoformat(), "days_ahead": (ad["start"] - now).days,
                                "kind": "dasha", "title": f"{md['lord']}–{ad['lord']} Antardasha begins", "weight": 3,
                                "note": "sub-period change — re-run this strategy and resize"})
                for pd_ in ad.get("pratyantardashas", []) or []:
                    if now <= pd_["start"] <= end:
                        out.append({"date": pd_["start"].date().isoformat(), "days_ahead": (pd_["start"] - now).days,
                                    "kind": "dasha", "title": f"{ad['lord']}–{pd_['lord']} Pratyantardasha", "weight": 1,
                                    "note": "short sub-sub-period — fine-tune timing"})
    except Exception:
        return out
    return out


def build_key_dates(events: List[Dict], alerts: List[Dict], dasha, extra: List[Dict]) -> List[Dict]:
    items: List[Dict] = []
    for e in events or []:
        if e.get("significance") != "High" and e.get("type") not in ("square", "opposition", "conjunction"):
            continue
        items.append({"date": e.get("date"), "days_ahead": int(_n(e.get("days_ahead"), 0)), "kind": "sky",
                      "title": e.get("event"), "weight": 2 if e.get("significance") == "High" else 1,
                      "note": (e.get("meaning") or e.get("description") or "")[:160]})
    for a in alerts or []:
        items.append({"date": a.get("date"), "days_ahead": int(_n(a.get("days_ahead"), 0)), "kind": "timing",
                      "title": a.get("title"), "weight": int(_n(a.get("strength"), 1)),
                      "note": a.get("note") or "Suri timing window — avoid new risk ±1 day"})
    items += dasha_dates(dasha) + (extra or [])
    last_seen: Dict[str, int] = {}
    out = []
    for it in sorted(items, key=lambda x: (x.get("date") or "", -x.get("weight", 0))):
        if not it.get("date"):
            continue
        title = str(it.get("title"))
        da = int(_n(it.get("days_ahead"), 0))
        # the same event repeated within a few days (e.g. multi-day lunar phases) counts once
        if title in last_seen and da - last_seen[title] <= 4:
            continue
        last_seen[title] = da
        out.append(it)
    return out


# =============================================================================
# 3. scoreboard
# =============================================================================

BASE_W = {"technical": 0.20, "quant": 0.12, "ml": 0.08, "suri": 0.12, "sky": 0.08,
          "agents": 0.18, "natal": 0.06, "dasha": 0.08, "transits": 0.08}


def scoreboard(inp: Dict) -> List[Dict]:
    """inp: dict of input name -> raw payload (or None when unavailable)."""
    rows: List[Dict] = []

    def add(key, name, score, reason, available=True, detail=None):
        score = round(_clip(_n(score)), 1) if available else 0.0
        rows.append({"key": key, "input": name, "available": available, "score": score,
                     "signal": _sig(score) if available else "n/a", "weight": BASE_W[key] if available else 0.0,
                     "reason": reason, "detail": detail})

    a = inp.get("analytics")
    if a and a.get("signal"):
        s = a["signal"]
        add("technical", "Technical consensus", s.get("score"),
            f"{s.get('label')} — {s.get('n_bull', 0)} bullish vs {s.get('n_bear', 0)} bearish pillars (trend, MACD, RSI, stochastic, volume…)")
    else:
        add("technical", "Technical consensus", 0, "Technical pack unavailable.", False)

    st = inp.get("stats")
    if st:
        sharpe = _n(st.get("sharpe")); cagr = _n(st.get("cagr")) * 100; mdd = _n(st.get("max_drawdown")) * 100
        regime = (a or {}).get("regime", "n/a")
        sc = _clip(sharpe * 35 - 8 + (cagr - 6) * 1.0 + (-10 if mdd < -35 else 0))
        add("quant", "Quant stats & regime", sc,
            f"3y CAGR {cagr:+.1f}%, Sharpe {sharpe:.2f}, max DD {mdd:.0f}%, {regime} regime (Hurst {(a or {}).get('hurst', 'n/a')})")
    else:
        add("quant", "Quant stats & regime", 0, "Quant stats unavailable.", False)

    ml = inp.get("ml")
    if ml and ml.get("available"):
        add("ml", "ML model zoo / ensemble", ml.get("score", 0), ml.get("reason", ""))
    else:
        add("ml", "ML model zoo / ensemble", 0,
            (ml or {}).get("reason") or "Not trained yet — train the model zoo (Model Lab) to include ML in this plan.", False)

    astro = inp.get("astro")
    if astro and astro.get("composite"):
        c = astro["composite"]; n_al = len(astro.get("timing_alerts") or [])
        add("suri", "Suri composite + timing", _n(c.get("composite")) * 1.5 - min(n_al, 4) * 2,
            f"Composite {_n(c.get('composite')):+.1f} ({c.get('zone')}), mood {_n((astro.get('mood') or {}).get('mood_index'), 50):.0f}/100, {n_al} timing alert(s) in 14 days")
    else:
        add("suri", "Suri composite + timing", 0, "Astro signal unavailable.", False)

    ev = inp.get("events")
    if ev is not None:
        near = [e for e in ev if _n(e.get("days_ahead"), 99) <= 45]
        hard = sum(1 for e in near if e.get("type") in ("square", "opposition"))
        soft = sum(1 for e in near if e.get("type") in ("trine", "sextile"))
        new_m = sum(1 for e in near if e.get("event") == "New Moon")
        sc = (soft - hard) * 8 + new_m * 3
        add("sky", "45-day sky events", sc,
            f"{len(near)} events: {soft} flowing vs {hard} hard aspects — "
            + ("smoother skies favour trend trades" if sc > 0 else "friction favours range/income trades" if sc < 0 else "balanced"))
    else:
        add("sky", "45-day sky events", 0, "Sky events unavailable.", False)

    ag = inp.get("agents")
    if ag and ag.get("decision"):
        d = ag["decision"]
        add("agents", "TradingAgents decision", d.get("score"),
            f"Portfolio Manager: {d.get('rating')} ({d.get('confidence')}% confidence) after the bull/bear and risk debates")
    else:
        add("agents", "TradingAgents decision", 0, "Agents unavailable.", False)

    nat = inp.get("natal")
    if nat:
        ranked = nat.get("ranked") or []
        top = [g for g, _ in ranked[:3]]
        avg_top = sum(v for _, v in ranked[:3]) / max(1, len(ranked[:3]))
        merc_jup = (_n(nat.get("scores", {}).get("Mercury")) + _n(nat.get("scores", {}).get("Jupiter"))) / 2
        add("natal", "Jataka natal strengths", (avg_top - 55) * 0.8 + (merc_jup - 50) * 0.4,
            f"Strongest grahas {', '.join(top)} (avg {avg_top:.0f}/100); Mercury/Jupiter (trading & wealth) average {merc_jup:.0f}")
    else:
        add("natal", "Jataka natal strengths", 0, "Natal chart unavailable.", False)

    ds = inp.get("dasha")
    if ds and ds.get("md"):
        fav = _n(ds.get("favour"), 1.0)
        add("dasha", "Current dasha (MD/AD/PD)", (fav - 1.0) * 120 + (_n(ds.get("ad_favour"), 1.0) - 1.0) * 60,
            f"{ds.get('md')} / {ds.get('ad')} / {ds.get('pd') or '-'} — favour ×{fav:.2f}; AD runs to {ds.get('ad_end')}")
    else:
        add("dasha", "Current dasha (MD/AD/PD)", 0, "Dasha unavailable.", False)

    tr = inp.get("transits")
    if tr:
        add("transits", "Today's transits over natal", tr.get("score"),
            f"{tr.get('favourable_count')} favourable gochar houses, {len(tr.get('activations') or [])} activation(s)"
            + (f"; {tr['flags'][0]['flag']}" if tr.get("flags") else ""))
    else:
        add("transits", "Today's transits over natal", 0, "Transit comparison unavailable.", False)
    return rows


def overall(rows: List[Dict], mult: Optional[Dict] = None) -> float:
    num = den = 0.0
    for r in rows:
        if not r["available"]:
            continue
        w = r["weight"] * (mult or {}).get(r["key"], 1.0)
        num += w * r["score"]; den += w
    return round(num / den, 1) if den else 0.0


# =============================================================================
# 4. horizon plans
# =============================================================================

def _stance(score: float) -> str:
    if score >= 30: return "Accumulate"
    if score >= 10: return "Lean long"
    if score > -10: return "Neutral — income first"
    if score > -30: return "Defensive"
    return "Avoid / hedge"


def _approach(stance: str, vol_ratio: float, days: int) -> List[str]:
    high_vol = vol_ratio > 1.2
    if stance == "Accumulate":
        a = ["Shares: buy in 3 tranches inside the entry zone",
             ("Put credit spreads (defined risk) below support" if high_vol else "Cash-secured puts at/below the entry zone")]
        if days >= 90: a.append("Covered calls on half the shares once target 1 is hit")
    elif stance == "Lean long":
        a = ["Shares: half-size starter position, add on a confirmed close above SMA20",
             "Cash-secured puts 1σ below spot (get paid to wait for a lower entry)"]
    elif stance.startswith("Neutral"):
        a = ["Covered calls on existing shares (30–45 DTE, ~0.25 delta)",
             ("Iron condors / put credit spreads, half size" if high_vol else "Cash-secured puts at support (the wheel)"),
             "Hold cash for better prices"]
    elif stance == "Defensive":
        a = ["Trim shares into strength; keep a small core",
             "Collar the core (sell call, buy put) or bear call spreads above resistance",
             "No naked short puts"]
    else:
        a = ["Exit / hedge most exposure", "Only defined-risk bearish spreads, tiny size", "Wait for the score to turn"]
    return a


def horizon_plans(rows: List[Dict], spot: float, analytics: Dict, key_dates: List[Dict],
                  capital: float, dasha: Dict, income: Dict) -> List[Dict]:
    a = analytics or {}
    sigma = (_n(a.get("sigma_pct"), 1.2) / 100) or 0.012
    vol_ratio = _n(a.get("vol_ratio"), 1.0)
    lv = {x.get("level"): _n(x.get("value")) for x in (a.get("levels") or [])}
    hi52 = lv.get("52-week high", spot * 1.15); lo52 = lv.get("52-week low", spot * 0.85)
    sma = {k: lv.get(k, spot) for k in ("SMA 20", "SMA 50", "SMA 200")}
    weekly_base = _n((income or {}).get("weekly_for_capital", {}).get("base"))
    plans = []
    prev_end = 0
    for days, label in HORIZONS:
        sc = overall(rows, H_MULT[days])
        stance = _stance(sc)
        h = math.sqrt(min(days, 252) * 252 / 365)  # trading days in window
        band = sigma * h
        supports = sorted([v for v in (sma["SMA 20"], sma["SMA 50"], sma["SMA 200"], lo52) if 0 < v < spot], reverse=True)
        long_bias = stance in ("Accumulate", "Lean long") or stance.startswith("Neutral")
        if long_bias:
            e_hi = spot * (1 - 0.15 * band)
            near_sup = next((s for s in supports if s <= e_hi and s >= spot * (1 - 0.9 * band)), None)
            e_lo = near_sup if near_sup else spot * (1 - 0.6 * band)
            stop = e_lo * (1 - 0.45 * band) if days < 365 else min(e_lo * (1 - 0.35 * band), sma["SMA 200"] * 0.97)
            t1 = spot * (1 + 0.6 * band)
            t2 = spot * (1 + 1.2 * band)
            if days <= 90 and hi52 > spot and t1 > hi52:
                t1 = hi52
        else:
            e_lo = spot * (1 + 0.1 * band); e_hi = spot * (1 + 0.5 * band)
            stop = e_hi * (1 + 0.4 * band)
            t1 = spot * (1 - 0.5 * band); t2 = max(lo52 * 0.98, spot * (1 - 1.0 * band))
        risk_pct = 0.01 if stance in ("Accumulate", "Lean long") else 0.0075 if stance.startswith("Neutral") else 0.005
        max_alloc = {"Accumulate": 0.25, "Lean long": 0.18}.get(stance, 0.12 if stance.startswith("Neutral") else 0.06)
        entry_mid = (e_lo + e_hi) / 2
        per_unit = abs(entry_mid - stop) or spot * 0.03
        units = min(capital * risk_pct / per_unit, capital * max_alloc / max(entry_mid, 1e-9))
        lo_d = prev_end
        dates = [d for d in key_dates if lo_d < _n(d.get("days_ahead"), -1) + 1 <= days]
        dates = sorted(dates, key=lambda d: (-d.get("weight", 0), d.get("date")))[: (6 if days < 365 else 8)]
        dates.sort(key=lambda d: d.get("date"))
        prev_end = days
        top_bull = max((r for r in rows if r["available"]), key=lambda r: r["score"] * H_MULT[days][r["key"]], default=None)
        top_bear = min((r for r in rows if r["available"]), key=lambda r: r["score"] * H_MULT[days][r["key"]], default=None)
        weeks = {30: 4.3, 60: 4.3, 90: 4.3, 365: 39}[days]
        income_focus = {
            30: "Ramp-up: open 1–2 small premium trades (≤50% of planned size) to learn the rhythm; bank no expectations.",
            60: "Build the ladder to ~75% of planned allocation; close winners at 50% of max profit.",
            90: "Full ladder running; review realised vs modelled weekly income and cut what isn't working.",
            365: "Steady-state: reinvest a share of income, rebalance at each dasha/ingress date, keep a 20% cash buffer.",
        }[days]
        ramp = {30: 0.4, 60: 0.75, 90: 1.0, 365: 1.0}[days]
        plans.append({
            "days": days, "label": label, "score": sc, "stance": stance,
            "signal": _sig(sc),
            "approach": _approach(stance, vol_ratio, days),
            "entry_low": round(min(e_lo, e_hi), 2), "entry_high": round(max(e_lo, e_hi), 2),
            "stop": round(stop, 2), "target_1": round(t1, 2), "target_2": round(t2, 2),
            "expected_range": [round(spot * (1 - band), 2), round(spot * (1 + band), 2)],
            "position": {"risk_pct": risk_pct * 100, "max_alloc_pct": max_alloc * 100,
                         "units": round(units, 2), "value": round(units * entry_mid, 0)},
            "key_dates": dates,
            "income_focus": income_focus,
            "income_band": {"low": round(_n((income or {}).get("weekly_for_capital", {}).get("low")) * weeks * ramp, 0),
                            "base": round(weekly_base * weeks * ramp, 0),
                            "high": round(_n((income or {}).get("weekly_for_capital", {}).get("high")) * weeks * ramp, 0)},
            "summary": (f"{label}: {stance} (score {sc:+.0f}). "
                        + (f"Strongest support from {top_bull['input'].lower()} ({top_bull['score']:+.0f})" if top_bull else "")
                        + (f"; main drag is {top_bear['input'].lower()} ({top_bear['score']:+.0f}). " if top_bear else ". ")
                        + (f"{'Buy' if long_bias else 'Sell/hedge'} between {_fmt(min(e_lo, e_hi))} and {_fmt(max(e_lo, e_hi))}, "
                           f"stop {_fmt(stop)}, targets {_fmt(t1)} / {_fmt(t2)}. ")
                        + (f"Mark {dates[0]['date']} ({dates[0]['title']}) in your calendar." if dates else "")),
        })
    return plans


# =============================================================================
# 5. income plan
# =============================================================================

def income_section(planner: Optional[Dict], capital: float, target_weekly: float,
                   dasha: Optional[Dict], plans: List[Dict]) -> Dict:
    from app.services.income_planner import ARCHETYPES, LADDER
    blend = {k: sum(b["weight"] * a["yield"][i] for b in LADDER for a in ARCHETYPES if a["key"] == b["key"])
             for i, k in enumerate(("low", "base", "high"))}
    annual = target_weekly * 52
    req = {k: round(annual / v) if v > 0 else None for k, v in blend.items()}
    wk = {k: round(capital * v / 52, 2) for k, v in blend.items()}
    out = {
        "capital": capital, "target_weekly": target_weekly, "annual_target": round(annual),
        "blended_yield": {k: round(v, 4) for k, v in blend.items()},
        "required_capital": req,  # low yield → MORE capital
        "weekly_for_capital": wk,
        "monthly_for_capital": {k: round(v * 52 / 12, 0) for k, v in wk.items()},
        "yearly_for_capital": {k: round(v * 52, 0) for k, v in wk.items()},
        "feasible_base": capital >= (req["base"] or 1e18),
        "gap_to_base": max(0, round((req["base"] or 0) - capital)),
        "ladder": [], "verdict": None,
        "planner_source": "income_planner (blended ladder yields)",
    }
    if planner and planner.get("success"):
        out["verdict"] = planner.get("verdict")
        out["max_sustainable_weekly"] = planner.get("max_sustainable_weekly")
        out["ladder"] = [{"label": l.get("label"), "weight": l.get("weight"), "allocation": l.get("allocation"),
                          "target_weekly": l.get("target_weekly"), "yield_base": l.get("yield_base")}
                         for l in planner.get("ladder", [])]
        out["capital_table"] = [{"label": t.get("label"), "capital_required": t.get("capital_required"),
                                 "risk": t.get("risk")} for t in planner.get("capital_table", [])]
    if dasha and dasha.get("favour"):
        out["dasha_note"] = (f"Your {dasha.get('md')} mahadasha favour factor is ×{_n(dasha.get('favour'), 1):.2f} — the Jataka "
                             "view scales expectations by it; we show the un-scaled market numbers here to stay conservative.")
    near = plans[0]["stance"] if plans else "Neutral — income first"
    out["explain"] = (
        f"To earn about £{target_weekly:,.0f}/week (£{annual:,.0f}/yr) from a balanced premium ladder you would need roughly "
        f"£{req['high']:,.0f} if things go well, £{req['base']:,.0f} in a normal year and £{req['low']:,.0f} if returns are poor. "
        f"With £{capital:,.0f} the same ladder models about £{wk['low']:,.0f}–£{wk['high']:,.0f}/week (base £{wk['base']:,.0f}). "
        + ("Your capital covers the base case." if out["feasible_base"] else
           f"You are £{out['gap_to_base']:,.0f} short of the base case — target £{wk['base']:,.0f}/week for now instead of forcing size.")
        + f" The near-term stance is “{near}”, so start with the instruments listed for the next 30 days."
    )
    return out


def weekly_routine(symbol_name: str, key_dates: List[Dict], plans: List[Dict], income: Dict) -> List[Dict]:
    wk = [d for d in key_dates if _n(d.get("days_ahead"), 99) <= 7]
    p = plans[0] if plans else {}
    return [
        {"day": "Monday", "task": f"Re-check the Final Strategy score and this week's dates"
                                  + (f" ({', '.join(d['date'] + ' ' + str(d['title']) for d in wk[:3])})" if wk else " (no major dates this week)")
                                  + "."},
        {"day": "Monday", "task": f"Confirm {symbol_name} is still inside the plan: entry {_fmt(p.get('entry_low', 0))}–{_fmt(p.get('entry_high', 0))}, stop {_fmt(p.get('stop', 0))}."},
        {"day": "Tue–Wed", "task": "Open new premium trades only away from timing-alert days; 30–45 DTE, ≤5% of capital per position."},
        {"day": "Daily", "task": "Close any option at 50% of max profit; exit at 2× the credit received. No exceptions."},
        {"day": "Thursday", "task": "Check upcoming sky events; halve new size into squares/oppositions and Full Moons."},
        {"day": "Friday", "task": f"Log realised income vs the modelled £{_n(income.get('weekly_for_capital', {}).get('base')):,.0f}/week base; note what worked."},
        {"day": "Weekend", "task": "Review drawdown: if the account is down >8% from peak, cut all sizes in half until it recovers."},
        {"day": "Monthly", "task": "Re-run the Agents debate and this plan after each antardasha/ingress date or a ±5% move."},
    ]


def bottom_line(symbol_name: str, score: float, plans: List[Dict], income: Dict, tr: Optional[Dict],
                ds: Optional[Dict], rows: List[Dict]) -> str:
    p30 = plans[0] if plans else {}; p365 = plans[-1] if plans else {}
    avail = sum(1 for r in rows if r["available"])
    bull = sum(1 for r in rows if r["available"] and r["signal"] == "bullish")
    bear = sum(1 for r in rows if r["available"] and r["signal"] == "bearish")
    tone = ("positive" if score >= 10 else "negative" if score <= -10 else "mixed")
    txt = (f"Bottom line for {symbol_name}: {avail} signals were combined — {bull} bullish, {bear} bearish — giving an overall "
           f"{tone} score of {score:+.0f}/100. For the next month the plan is “{p30.get('stance', '-')}”: "
           f"{'buy' if p30.get('signal') != 'bearish' else 'trim/hedge'} only between {_fmt(p30.get('entry_low', 0))} and "
           f"{_fmt(p30.get('entry_high', 0))} with a stop at {_fmt(p30.get('stop', 0))}. Over the year the stance is "
           f"“{p365.get('stance', '-')}”. ")
    if ds and ds.get("md"):
        txt += f"Your {ds['md']}–{ds['ad']} dasha runs until {ds.get('ad_end')}; re-plan at that date. "
    if tr and tr.get("flags"):
        txt += tr["flags"][0]["text"] + " "
    txt += (f"For income, £{income.get('target_weekly', 500):,.0f}/week needs about £{(income.get('required_capital') or {}).get('base', 0):,.0f} "
            f"in a normal year; with £{income.get('capital', 0):,.0f} expect roughly £{_n((income.get('weekly_for_capital') or {}).get('base')):,.0f}/week "
            "on average, with losing weeks included. Illustrative only — not a promise and not financial advice.")
    return txt
