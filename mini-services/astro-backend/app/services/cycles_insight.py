"""
Suri Cycles — layman insight layer (v1.3)
=========================================
Turns the Suri engine's numbers (mood, composite, reversal / volatility
windows, range ladder) plus the cycle clock, the symbol's historical cycle
statistics and the upcoming event studies into:

  * a plain-English "Today's reading" (sky now -> price now -> meaning -> action)
  * an inline explanation for every metric, written from today's values
  * a cycle clock (lunar, solar, retrograde and Jupiter-Saturn cycles)
  * a concrete 7-day plan and a data-backed 30-day lunar calendar

Every sentence is generated from data. Educational only — not advice.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.services.cycles_sky import (NAK_LORDS, NAKSHATRAS, PHASES8, RASHI, RETRO_PLANETS, SIGNS, SKY,
                                     tithi_name)
from app.services.cycles_stats import fmt_date, fnum

CRYPTO_SECTORS = {"Layer 1", "Majors", "Meme", "Oracle"}


def _days(a: int, b: Optional[int]) -> Optional[int]:
    return None if b is None else int(b - a)


def _next_event(prefix: str, after: int) -> Optional[Dict]:
    for e in SKY.events():
        if e["i"] > after and e["key"].startswith(prefix):
            return e
    return None


def _prev_event(prefix: str, upto: int) -> Optional[Dict]:
    best = None
    for e in SKY.events():
        if e["i"] > upto:
            break
        if e["key"].startswith(prefix):
            best = e
    return best


# ---------------------------------------------------------------------------
# cycle clock
# ---------------------------------------------------------------------------
def cycle_clock() -> Dict:
    SKY.ensure()
    t = SKY.today_idx()
    el = float(SKY.elong[t])
    tithi = int(SKY.tithi[t])
    nk = int(SKY.nakshatra[t])
    nm = _next_event("lunation:new", t)
    fm = _next_event("lunation:full", t)
    waxing = el < 180
    nxt_turn = fm if waxing else nm
    lunar = {
        "id": "lunar", "label": "Lunar cycle (tithi)", "progress": fnum(el / 360.0, 3),
        "state": f"{PHASES8[int(SKY.phase8[t])]} · {tithi_name(tithi)} (tithi {tithi}/30)",
        "detail": f"{'Shukla (waxing)' if waxing else 'Krishna (waning)'} paksha · Moon in {NAKSHATRAS[nk]} (lord {NAK_LORDS[nk]})",
        "next_label": "Full Moon" if waxing else "New Moon",
        "next_date": nxt_turn["date"] if nxt_turn else None, "days_to_next": _days(t, nxt_turn["i"] if nxt_turn else None),
        "meaning": (f"Day {tithi} of the 30-tithi month. "
                    + ("Waxing half: classically the accumulation phase — optimism builds toward the Full Moon"
                       if waxing else "Waning half: classically the distribution phase — profit-taking into the New Moon")
                    + (f"; next turning point is the {'Full' if waxing else 'New'} Moon on {fmt_date(nxt_turn['date'])}." if nxt_turn else "."))
        , "extra": {"next_new": nm["date"] if nm else None, "next_full": fm["date"] if fm else None,
                    "nakshatra": NAKSHATRAS[nk], "tithi": tithi, "paksha": "Shukla" if waxing else "Krishna"},
    }
    sun_lon = float(SKY.lon["Sun"][t])
    sg = int(sun_lon // 30)
    sk = _next_event("ingress:Sun:", t)
    solar = {
        "id": "solar", "label": "Solar month (Sankranti)", "progress": fnum((sun_lon % 30) / 30.0, 3),
        "state": f"Sun in {SIGNS[sg]} ({RASHI[sg]}) {sun_lon % 30:.1f}°",
        "detail": "Sidereal (Lahiri) solar month — the Vedic seasonal calendar",
        "next_label": f"Sun enters {sk['into']}" if sk else "Next Sankranti",
        "next_date": sk["date"] if sk else None, "days_to_next": _days(t, sk["i"] if sk else None),
        "meaning": (f"{sun_lon % 30:.0f} of 30 degrees through the {RASHI[sg]} month"
                    + (f"; {RASHI[(sg + 1) % 12]} Sankranti on {fmt_date(sk['date'])} starts the next seasonal theme." if sk else ".")),
    }
    items = [lunar, solar]
    for p in RETRO_PLANETS:
        retro = bool(SKY.retro[p][t])
        nxt = _next_event(f"station:{p}:", t)
        prv = _prev_event(f"station:{p}:", t)
        prog = 0.0
        if nxt and prv and nxt["i"] > prv["i"]:
            prog = (t - prv["i"]) / (nxt["i"] - prv["i"])
        lon = float(SKY.lon[p][t])
        if retro:
            meaning = (f"{p} is retrograde (apparently moving backwards) — its themes ({_THEME[p]}) are under review"
                       + (f" until it turns direct on {fmt_date(nxt['date'])}." if nxt else "."))
        else:
            meaning = (f"{p} is direct — normal forward motion"
                       + (f"; next retrograde station on {fmt_date(nxt['date'])}." if nxt else "."))
        items.append({
            "id": p.lower(), "label": f"{p} retrograde cycle", "progress": fnum(prog, 3),
            "state": f"{'℞ Retrograde' if retro else 'Direct'} in {SIGNS[int(lon // 30)]} {lon % 30:.1f}°",
            "detail": f"Since {fmt_date(prv['date'])}" if prv else "",
            "next_label": f"Turns {'direct' if retro else 'retrograde'}",
            "next_date": nxt["date"] if nxt else None, "days_to_next": _days(t, nxt["i"] if nxt else None),
            "retro": retro, "meaning": meaning,
        })
    js = SKY.jupiter_saturn()
    sep = js.get("separation", 0.0)
    cands = [(js.get(f"next_{k}"), k) for k in ("conjunction", "opposition", "square") if js.get(f"next_{k}")]
    cands.sort()
    nxt_js = cands[0] if cands else (None, "")
    today = datetime.utcnow().date()
    items.append({
        "id": "jupsat", "label": "Jupiter–Saturn cycle (~20 yr)", "progress": fnum(sep / 360.0, 3),
        "state": f"{sep:.0f}° apart (last conjunction {fmt_date(js.get('last_conjunction'))} {str(js.get('last_conjunction', ''))[:4]})",
        "detail": "The 'great conjunction' cycle — long-wave economic and political regime",
        "next_label": f"Jupiter–Saturn {nxt_js[1]}" if nxt_js[0] else "",
        "next_date": nxt_js[0],
        "days_to_next": (date.fromisoformat(nxt_js[0]) - today).days if nxt_js[0] else None,
        "meaning": (f"{sep:.0f}° into the 20-year cycle that began at the Dec 2020 great conjunction"
                    + (f"; next milestone is the {nxt_js[1]} around {fmt_date(nxt_js[0])} {nxt_js[0][:4]}" if nxt_js[0] else "")
                    + (" — the half-way 'peak tension' point of the cycle." if nxt_js[1] == "opposition" else
                       f"; the opposition (half-way 'peak tension') follows around {str(js.get('next_opposition', ''))[:4]}."
                       if js.get("next_opposition") else ".")),
        "extra": js,
    })
    return {"date": SKY.date_of(t), "items": items}


_THEME = {"Mercury": "communication, contracts, tech", "Venus": "consumption, luxury, money values",
          "Mars": "energy, metals, aggression", "Jupiter": "growth, credit, optimism",
          "Saturn": "structure, debt, regulation"}


# ---------------------------------------------------------------------------
# explanations
# ---------------------------------------------------------------------------
def _rsi_desc(rsi: float) -> str:
    return ("overbought — late to chase" if rsi >= 70 else "strong momentum" if rsi >= 60 else
            "neutral" if rsi > 40 else "weak momentum" if rsi > 30 else "oversold — bounce-prone")


def explain(signal: Dict, name: str) -> Dict[str, str]:
    mood = signal.get("mood", {})
    comp = signal.get("composite", {}) or {}
    rev = signal.get("reversal", {})
    vol = signal.get("volatility", {})
    rng = signal.get("five_day_range", {}) or {}
    c = mood.get("components", {})
    m = mood.get("mood_index", 50)
    out: Dict[str, str] = {}
    out["mood"] = (
        f"Sky-mood {m:.0f}/100 ({mood.get('mood_label', '')}). It averages four sky inputs: lunar phase "
        f"{c.get('lunar_phase', 0):.0f} ({mood.get('lunar', '')} Moon), retrograde load {c.get('retro_load', 0):.0f} "
        f"({mood.get('retrogrades', 0)} of 5 planets retrograde — each one lowers it), planetary dignity "
        f"{c.get('dignity', 0):.0f} and Moon speed {c.get('moon_velocity', 0):.0f}. Above 58 = sky supportive, "
        f"45–58 neutral, below 45 cautious. It describes the sky, not {name}'s price.")
    if comp:
        out["composite"] = (
            f"{comp.get('composite', 0):+.0f} on a −100…+100 dial = 55% price technicals "
            f"({comp.get('technical_score', 0):+.0f}: RSI {comp.get('rsi14', 0):.0f}, trend {comp.get('trend_pct', 0):+.2f}%, "
            f"volatility percentile {comp.get('vol_percentile', 0) * 100:.0f}) + 45% sky mood ({comp.get('astro_score', 0):+.0f}). "
            f"+15 or higher = Buy zone, −15 or lower = Sell zone, in between = Neutral. Now: {comp.get('zone', '')}.")
        out["rsi"] = (f"RSI14 {comp.get('rsi14', 0):.0f}: momentum gauge 0–100 — {_rsi_desc(comp.get('rsi14', 50))}. "
                      "Above 70 overbought, below 30 oversold.")
        out["trend"] = (f"Trend {comp.get('trend_pct', 0):+.2f}% = how far the 20-day average sits above (+) or below (−) "
                        f"the 50-day average. Positive = uptrend, negative = downtrend.")
        out["vol"] = (f"Volatility {comp.get('vol20_annualised', 0) * 100:.1f}% a year (last 20 sessions) — higher than "
                      f"{comp.get('vol_percentile', 0) * 100:.0f}% of the past year's readings. Above 70% the composite is penalised.")
    rs = rev.get("reversal_score", 0)
    drivers = "; ".join(d["detail"] for d in rev.get("drivers", [])[:3])
    out["reversal"] = (
        f"Reversal score {rs:.0f}/100 counts today's classical turning-point triggers: Moon at a hard angle to the Sun, "
        f"New/Full Moon ±1 day, a planet stationing within 2–3 days, a sign change within 1–2 days. "
        + (f"Active now: {drivers}. " if drivers else "None is active today, ")
        + ("so trends tend to continue — no reason to expect a turn today." if rs < 25 else
           "a few triggers — watch for intraday reversals; don't chase breakouts." if rs < 55 else
           "many triggers — a reversal-prone session: take partial profits and avoid new entries."))
    vs = vol.get("volatility_score", 0)
    vdrivers = "; ".join(d["detail"] for d in vol.get("drivers", [])[:3])
    out["volatility"] = (
        f"Volatility window {vs:.0f}/100 flags sky set-ups linked to bigger swings: New/Full Moon ±2 days, Mars/Saturn "
        f"stations, a Rahu–Ketu sign change, a slow Moon. "
        + (f"Active now: {vdrivers}. " if vdrivers else "None is active, ")
        + ("so normal position sizes are fine." if vs < 35 else "consider trimming size by a quarter." if vs < 55
           else "cut size and widen stops today."))
    if rng.get("bands"):
        b = rng["bands"]
        dv = rng.get("ewma_daily_vol", 0) * 100
        out["range"] = (
            f"Expected 5-session range from recent volatility ({dv:.2f}%/day, EWMA) × sky multiplier "
            f"{rng.get('astro_multiplier', 1):.2f}. R {b['outer']['high']:,} / S {b['outer']['low']:,} are ±1σ: price "
            f"finishes the 5 sessions inside them ~68% of the time — use S as the stop-loss area and R as the profit target. "
            f"inner R {b['inner']['high']:,} / inner S {b['inner']['low']:,} are ±½σ (~38% inside): the first target "
            f"and the dip-buy zone.")
    return out


# ---------------------------------------------------------------------------
# today's reading
# ---------------------------------------------------------------------------
def _current_edges(stats: Optional[Dict]) -> List[Dict]:
    """Historical stats for the cycle states that are active today."""
    if not stats or not stats.get("success"):
        return []
    edges = []
    for sec, label in (("moon_phase", "moon phase"), ("nakshatra", "Moon nakshatra"), ("paksha", "paksha"),
                       ("sun_sign", "Sun sign")):
        s = stats[sec]
        row = next((r for r in s["rows"] if r["label"] == s.get("current")), None)
        if row:
            edges.append({"what": f"{label} {row['label']}", "row": row, "base": s["baseline"]})
    for p, r in stats["retrograde"].items():
        if r.get("now") == "retrograde" and "mean_pct" in r.get("retro", {}):
            edges.append({"what": f"{p} retrograde", "row": {**r["retro"], "t": r["t"], "verdict": r["verdict"],
                                                              "label": f"{p} retrograde"},
                          "base": r["direct"]})
    edges.sort(key=lambda e: -abs(e["row"].get("t", 0)))
    return edges


def todays_reading(signal: Dict, clock: Dict, stats: Optional[Dict], events: Optional[Dict],
                   name: str, ctx: Dict) -> Dict:
    mood = signal.get("mood", {})
    comp = signal.get("composite", {}) or {}
    rng = signal.get("five_day_range", {}) or {}
    rev = signal.get("reversal", {}).get("reversal_score", 0)
    lunar = clock["items"][0]
    retro_now = [it["label"].split()[0] for it in clock["items"] if it.get("retro")]
    sentences: List[str] = []

    # 1. sky now
    retro_txt = (f"{', '.join(retro_now)} {'is' if len(retro_now) == 1 else 'are'} retrograde"
                 if retro_now else "no planet is retrograde")
    nxt = f"; next {lunar['next_label']} {fmt_date(lunar['next_date'])}" if lunar.get("next_date") else ""
    sentences.append(
        f"Sky now: the Moon is {lunar['state'].split(' · ')[0].lower()} in {lunar['extra']['nakshatra']} "
        f"({lunar['extra']['paksha']} paksha{nxt}) and {retro_txt}; the sky-mood reads {mood.get('mood_index', 50):.0f}/100 "
        f"({mood.get('mood_label', 'Neutral').lower()}).")

    # 2. price now
    trend = comp.get("trend_pct", 0.0)
    rsi = comp.get("rsi14", 50.0)
    tdesc = ("in an uptrend" if trend > 0.5 else "in a downtrend" if trend < -0.5 else "moving sideways")
    sentences.append(
        f"Price now: {name} is {tdesc} (20-day average {trend:+.1f}% vs the 50-day), RSI {rsi:.0f} "
        f"({_rsi_desc(rsi)}), volatility {ctx.get('vol_state', 'normal')} at {ctx.get('vol21_pct', 0):.0f}% a year.")

    # 3. what it means for this stock (history)
    edges = _current_edges(stats)
    strong = [e for e in edges if e["row"].get("verdict") in ("significant", "weak")]
    zone = comp.get("zone", "Neutral")
    if strong:
        e = strong[0]
        r = e["row"]
        good = r.get("mean_pct", 0) > e["base"].get("mean_pct", 0)
        sentences.append(
            f"For {name}: the composite is {comp.get('composite', 0):+.0f} ({zone}). Of today's cycles, {e['what']} has the "
            f"clearest history — {r.get('hit_pct', 0):.0f}% up days vs {e['base'].get('hit_pct', 0):.0f}% normally, a "
            f"{'mild tailwind' if good else 'mild headwind'} ({'statistically meaningful' if r['verdict'] == 'significant' else 'weak, could be chance'}).")
    else:
        sentences.append(
            f"For {name}: the composite is {comp.get('composite', 0):+.0f} ({zone}). None of today's cycle states "
            f"(moon phase, nakshatra, paksha, Sun sign, retrogrades) has a reliable historical edge for this stock, "
            f"so price structure should lead.")

    # 4. action
    acts: List[str] = []
    b = (rng.get("bands") or {})
    iS = b.get("inner", {}).get("low")
    iR = b.get("inner", {}).get("high")
    S = b.get("outer", {}).get("low")
    R = b.get("outer", {}).get("high")
    bias = "Neutral"
    if iS and S:
        if zone in ("Buy", "Strong Buy") and ctx.get("trend") != "down":
            bias = "Bullish"
            acts.append(f"Wait for a dip toward {iS:,.2f} before adding; first target {iR:,.2f}, stretch {R:,.2f}; "
                        f"keep a stop below {S:,.2f}")
        elif zone in ("Sell", "Strong Sell") or (zone == "Neutral" and ctx.get("trend") == "down" and trend < 0):
            bias = "Bearish"
            acts.append(f"Avoid new longs; use rallies toward {iR:,.2f} to trim or hedge; a close below {S:,.2f} "
                        f"opens more downside")
        else:
            acts.append(f"Trade the range: buy only near {iS:,.2f}, trim near {iR:,.2f}; stand aside if price closes "
                        f"outside {S:,.2f}–{R:,.2f}")
    # avoid-dates: next high-importance event within 14 days, prefer the most volatile in history
    avoid = None
    if events and events.get("events"):
        horizon = (datetime.utcnow().date() + timedelta(days=14)).isoformat()
        cands = [e for e in events["events"] if e["importance"] == "High" and e["date"] <= horizon]
        cands.sort(key=lambda e: (-(e["study"].get("vol_ratio", 1.0)), e["date"]))
        if cands:
            avoid = cands[0]
            acts.append(f"avoid opening new positions around {fmt_date(avoid['date'])} ({avoid['title']})"
                        + (f" — historically {avoid['study']['vol_ratio']:.2f}× normal volatility for {name}"
                           if avoid["study"].get("vol_ratio", 1) >= 1.05 else ""))
    if rev >= 55 or ctx.get("vol_state") == "elevated" or (avoid and avoid["study"].get("vol_ratio", 1) >= 1.15):
        acts.append("tighten stops")
    if acts:
        a = "; ".join(acts)
        sentences.append("What to do: " + a[0].lower() + a[1:] + ".")
    return {"sentences": sentences, "bias": bias,
            "levels": {"inner_support": iS, "inner_resistance": iR, "support": S, "resistance": R},
            "avoid": {"date": avoid["date"], "title": avoid["title"]} if avoid else None}


# ---------------------------------------------------------------------------
# 7-day plan and 30-day lunar calendar
# ---------------------------------------------------------------------------
def _nak_row(stats: Optional[Dict], k: int) -> Optional[Dict]:
    if not stats or not stats.get("success"):
        return None
    return stats["nakshatra"]["rows"][k]


def _phase_row(stats: Optional[Dict], k: int) -> Optional[Dict]:
    if not stats or not stats.get("success"):
        return None
    return stats["moon_phase"]["rows"][k]


def _edge_note(row: Optional[Dict], base_hit: float) -> str:
    if not row or not row.get("n"):
        return "no history"
    tag = {"significant": "meaningful", "weak": "weak hint", "noise": "noise", "too few": "too few days"}[row["verdict"]]
    return f"{row['hit_pct']:.0f}% up days (avg {base_hit:.0f}%) — {tag}"


def week_plan(signal: Dict, stats: Optional[Dict], events: Optional[Dict], name: str, ctx: Dict,
              crypto: bool) -> Dict:
    t = SKY.today_idx()
    comp = signal.get("composite", {}) or {}
    zone = comp.get("zone", "Neutral")
    rng = signal.get("five_day_range", {}) or {}
    b = rng.get("bands") or {}
    base_hit = stats["nakshatra"]["baseline"]["hit_pct"] if stats and stats.get("success") else 50.0
    ev_by_day: Dict[str, List[Dict]] = {}
    for e in (events or {}).get("events", []):
        ev_by_day.setdefault(e["date"], []).append(e)
    days = []
    carry: List[Dict] = []  # weekend/holiday events roll onto the next session
    for k in range(7):
        i = t + k
        d = date.fromisoformat(SKY.date_of(i))
        wk = d.weekday() >= 5 and not crypto
        nk = int(SKY.nakshatra[i])
        row = _nak_row(stats, nk)
        evs = ev_by_day.get(d.isoformat(), [])
        if wk:
            carry += evs
            evs_eff = []
        else:
            evs_eff = carry + evs
            carry = []
        hi = [e for e in evs_eff if e["importance"] == "High"]
        if wk:
            todo = "Market closed — review the plan."
        elif hi:
            e0 = max(hi, key=lambda e: e["study"].get("vol_ratio", 1))
            wkd = " (over the weekend)" if e0 not in evs else ""
            todo = (f"{e0['title']}{wkd}: no fresh entries; " +
                    ("tighten stops." if e0["study"].get("vol_ratio", 1) >= 1.05 else "hold the plan, the event has no strong history."))
        elif row and row["verdict"] in ("significant", "weak") and row["diff_pct"] > 0 and zone not in ("Sell", "Strong Sell"):
            todo = f"Historically firmer day ({NAKSHATRAS[nk]}): OK to add on a dip toward {b.get('inner', {}).get('low', 0):,.2f}."
        elif row and row["verdict"] in ("significant", "weak") and row["diff_pct"] < 0:
            todo = f"Historically softer day ({NAKSHATRAS[nk]}): avoid chasing; trim strength near {b.get('inner', {}).get('high', 0):,.2f}."
        elif zone in ("Buy", "Strong Buy"):
            todo = "Routine day: hold longs; buy only on dips."
        elif zone in ("Sell", "Strong Sell"):
            todo = "Routine day: stay light; sell into bounces."
        else:
            todo = "Routine day: range rules — small size."
        days.append({
            "date": d.isoformat(), "weekday": d.strftime("%a"), "closed": wk,
            "phase": PHASES8[int(SKY.phase8[i])], "tithi": tithi_name(int(SKY.tithi[i])),
            "nakshatra": NAKSHATRAS[nk], "events": [e["title"] for e in evs],
            "carried": [e["title"] for e in evs_eff if e not in evs],
            "top": (sorted(evs_eff, key=lambda e: {"High": 0, "Medium": 1}.get(e["importance"], 2))[0]["title"]
                    if evs_eff else None),
            "history": _edge_note(row, base_hit), "verdict": row["verdict"] if row else "too few", "todo": todo,
        })
    lead = ("lean long but buy dips only" if zone in ("Buy", "Strong Buy") else
            "stay defensive — sell rallies, keep stops" if zone in ("Sell", "Strong Sell") else "trade the range with small size")
    key_days = [f"{x['weekday']} {fmt_date(x['date'])} ({x['top']})" for x in days if x["top"] and not x["closed"]]
    playbook = (f"This week for {name}: the composite is {zone} and the trend is {ctx.get('trend', 'sideways')}, so {lead}. "
                + (f"Expected 5-session range {b['outer']['low']:,.2f} – {b['outer']['high']:,.2f}; " if b else "")
                + (f"dates to respect: {', '.join(key_days[:4])}." if key_days else "no major sky events this week — routine levels apply."))
    return {"playbook": playbook, "days": days}


def lunar_calendar(stats: Optional[Dict], name: str, crypto: bool) -> Dict:
    t = SKY.today_idx()
    base_hit = stats["nakshatra"]["baseline"]["hit_pct"] if stats and stats.get("success") else 50.0
    out = []
    best, worst = [], []
    for k in range(30):
        i = t + k
        d = date.fromisoformat(SKY.date_of(i))
        nk = int(SKY.nakshatra[i])
        ph = int(SKY.phase8[i])
        row = _nak_row(stats, nk)
        prow = _phase_row(stats, ph)
        closed = d.weekday() >= 5 and not crypto
        tilt = 0
        if row and row["verdict"] in ("significant", "weak"):
            tilt = 1 if row["diff_pct"] > 0 else -1
        el = float(SKY.elong[i])
        lore = ("accumulation phase" if el < 90 else "momentum phase" if el < 180 else
                "distribution phase" if el < 270 else "wash-out phase")
        note = f"{lore}; {NAKSHATRAS[nk]}: {_edge_note(row, base_hit)}"
        if prow and prow["verdict"] in ("significant", "weak"):
            note += f"; {PHASES8[ph]} phase {prow['hit_pct']:.0f}% up days ({prow['verdict']})"
        item = {"date": d.isoformat(), "weekday": d.strftime("%a"), "closed": closed, "phase": PHASES8[ph],
                "tithi": tithi_name(int(SKY.tithi[i])), "nakshatra": NAKSHATRAS[nk], "angle": fnum(el, 1),
                "hit_pct": row["hit_pct"] if row else None, "verdict": row["verdict"] if row else "too few",
                "tilt": tilt, "note": note}
        out.append(item)
        if not closed and tilt > 0:
            best.append(item)
        if not closed and tilt < 0:
            worst.append(item)
    if best or worst:
        summary = (f"Over the next 30 days, the Moon's path gives {name} "
                   + (f"historically firmer days on {', '.join(fmt_date(x['date']) for x in best[:5])}" if best else "no historically firmer days")
                   + (f" and softer days on {', '.join(fmt_date(x['date']) for x in worst[:5])}" if worst else "")
                   + ". These are weak, statistical tilts — use them to time entries you already planned, not to create trades.")
    else:
        summary = (f"No nakshatra in the next 30 days has a reliable historical tilt for {name}; the classical rule of "
                   "thumb (accumulate New→Full, harvest Full→New) is shown for context only.")
    return {"summary": summary, "days": out}
