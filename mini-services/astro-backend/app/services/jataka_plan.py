"""
Jataka money plan (v1.3): wealth houses & their lords, a composite planet
strength, market / sector / strategy fit scores with reasons, illustrative
income bands and an illustrative lifetime £ wealth projection modulated by the
Vimshottari dasha sequence.

Everything here is EDUCATIONAL and ILLUSTRATIVE. Fit scores are a transparent
weighting of classical strength signals; return ranges are broad long-run
historical reference ranges per strategy family, not forecasts.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.services.astro_data import SIGN_LORDS

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
GRAHAS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]
YEAR = 365.2425

WEALTH_HOUSE_THEMES = {
    2: ("Savings & family wealth", "what you keep: bank balance, accumulated assets, value investing"),
    5: ("Speculation & intelligence", "trading, options, short-term bets and creative ideas"),
    8: ("Other people's money", "sudden gains/losses, inheritance, insurance, leverage, research"),
    9: ("Fortune & luck", "long-horizon investing, mentors, foreign/long-distance fortune"),
    11: ("Gains & income streams", "realised profits, networks, recurring income"),
}

# ── market / sector / strategy models: (planet or "H<n>") → weight ──
MARKETS = {
    "India (NSE/BSE)": ({"Jupiter": .3, "Sun": .25, "Moon": .2, "Saturn": .1, "H9": .15},
                         "Jupiter/Sun/Moon rule India's banks, PSUs and consumption story"),
    "US (S&P 500 / NASDAQ)": ({"Mercury": .3, "Rahu": .3, "Jupiter": .2, "Sun": .2},
                               "Mercury/Rahu drive the US tech and innovation premium"),
    "UK (FTSE)": ({"Saturn": .35, "Venus": .35, "Moon": .15, "Jupiter": .15},
                  "Saturn/Venus suit the FTSE's value, banks, miners and consumer staples"),
    "Global / Emerging (ETFs)": ({"Rahu": .3, "H12": .25, "H9": .2, "Jupiter": .25},
                                 "Rahu + 9th/12th houses (foreign lands) favour diversified global exposure"),
    "Crypto": ({"Rahu": .45, "Mercury": .25, "Mars": .2, "H5": .1},
               "Rahu rules unconventional, speculative, tech-native assets"),
    "Commodities (gold, oil, metals)": ({"Mars": .35, "Saturn": .3, "Sun": .2, "Moon": .15},
                                        "Mars (metals/energy), Saturn (mining), Sun (gold), Moon (silver)"),
}
SECTORS = {
    "BFSI (banks, insurers, NBFCs)": {"Jupiter": .5, "Venus": .2, "H2": .15, "H11": .15},
    "FMCG / consumer staples": {"Moon": .5, "Venus": .3, "Mercury": .2},
    "Metals, mining, energy & utilities (MLEU)": {"Mars": .4, "Saturn": .35, "Sun": .25},
    "IT / CMT (tech, telecom, media)": {"Mercury": .55, "Rahu": .3, "Moon": .15},
    "Pharma & healthcare": {"Moon": .3, "Ketu": .25, "Jupiter": .25, "Sun": .2},
    "Auto & auto ancillaries": {"Venus": .5, "Mars": .3, "Saturn": .2},
    "Infrastructure & capital goods": {"Saturn": .5, "Mars": .3, "Sun": .2},
    "Realty": {"Mars": .45, "Venus": .25, "Moon": .15, "H4": .15},
    "PSU / government-linked": {"Sun": .6, "Saturn": .2, "Jupiter": .2},
}
# (weights, annual return range low/base/high — broad historical reference, why)
STRATEGIES = {
    "long_term_equity": ("Long-term equity investing", {"Jupiter": .35, "Saturn": .25, "Venus": .2, "H2": .2},
                         (0.04, 0.09, 0.14), "buy quality, hold for years; needs patience (Jupiter/Saturn) and a strong 2nd house"),
    "swing": ("Swing trading (days–weeks)", {"Mars": .35, "Mercury": .3, "Sun": .2, "H3": .15},
              (-0.05, 0.12, 0.28), "needs decisiveness (Mars), analysis (Mercury) and courage (3rd house)"),
    "intraday": ("Intraday trading", {"Mercury": .35, "Moon": .25, "Mars": .25, "H3": .15},
                 (-0.20, 0.06, 0.30), "speed + emotional control; most retail day-traders lose money, so this needs a very strong Moon/Mercury"),
    "options_selling": ("Options selling (income, defined risk)", {"Saturn": .3, "Venus": .3, "Mercury": .25, "H8": .15},
                        (0.00, 0.10, 0.18), "acting like the insurer (8th house) with Saturn's discipline; steady but with tail risk"),
    "options_buying": ("Options buying (directional)", {"Rahu": .35, "Mars": .3, "H5": .35},
                       (-0.45, -0.02, 0.60), "pure speculation (5th house, Rahu); lottery-like payoff, most premiums expire worthless"),
    "fixed_income": ("Fixed income (bonds, gilts, deposits)", {"Saturn": .4, "Moon": .3, "H2": .3},
                     (0.03, 0.045, 0.06), "capital safety; suits a strong Saturn/Moon and the 2nd house of savings"),
    "quant_astro": ("Institutional quant-astro (like this product)", {"Mercury": .35, "Jupiter": .2, "Saturn": .2, "Ketu": .1, "H10": .15},
                    (-0.02, 0.10, 0.22), "systematic, model-driven, rules-first; Mercury (models), Saturn (process), Ketu (research)"),
}

DIGNITY_PTS = {"exalted": 100, "moolatrikona": 88, "own sign": 78, "friendly sign": 60,
               "neutral": 48, "neutral node": 50, "debilitated": 18}


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def composite_strength(positions: Dict, strengths: Dict, analysis: Dict) -> Dict[str, Dict]:
    """0-100 per graha: 50% placement score, 30% shadbala ratio, 20% D9 dignity."""
    shad = (analysis.get("shadbala") or {}).get("planets", {})
    vargas = ((analysis.get("vargas") or {}).get("planets")) or {}
    d9pts = {"exalted": 100, "moolatrikona": 85, "own": 78, "friend": 60, "neutral": 45, "enemy": 30, "debilitated": 15}
    out = {}
    for g in GRAHAS:
        base = float(strengths["scores"].get(g, 40))
        parts = {"placement": base}
        sc = 0.5 * base
        if g in shad and shad[g].get("required"):
            ratio = shad[g]["rupas"] / shad[g]["required"]
            sb = _clip(ratio / 1.6 * 100, 5, 100)
            parts["shadbala"] = round(sb)
            sc += 0.3 * sb
        else:
            sc += 0.3 * base
        d9 = vargas.get(g, {}).get("vargas", {}).get("D9", {}).get("dignity")
        if d9 in d9pts:
            parts["navamsa"] = d9pts[d9]
            sc += 0.2 * d9pts[d9]
        else:
            sc += 0.2 * base
        if positions[g].get("combust"):
            sc -= 6
            parts["combust"] = -6
        out[g] = {"score": round(_clip(sc, 3, 99)), "parts": parts}
    return out


def house_strength(h: int, positions: Dict, lag: int, comp: Dict, sav: List[int]) -> float:
    sign = (lag + h - 1) % 12
    lord = SIGN_LORDS[sign]
    lord_h = positions[lord]["house"]
    s = 0.55 * comp[lord]["score"]
    s += 8 if lord_h in (1, 4, 7, 10, 5, 9, 2, 11) else (-8 if lord_h in (6, 8, 12) else 0)
    occ = [g for g in GRAHAS if positions[g]["house"] == h]
    s += sum(5 if g in ("Jupiter", "Venus", "Mercury", "Moon") else -2 for g in occ)
    if sav:
        s += (sav[sign] - 28) * 2.2 + 25
    else:
        s += 25
    return _clip(s, 5, 99)


def wealth_houses(positions: Dict, lag: int, comp: Dict, sav: List[int]) -> List[Dict]:
    rows = []
    for h, (title, theme) in WEALTH_HOUSE_THEMES.items():
        sign = (lag + h - 1) % 12
        lord = SIGN_LORDS[sign]
        lp = positions[lord]
        occ = [g for g in GRAHAS if positions[g]["house"] == h]
        score = round(house_strength(h, positions, lag, comp, sav))
        tone = "strong" if score >= 62 else "average" if score >= 45 else "weak"
        bind = sav[sign] if sav else None
        plain = (f"House {h} ({title.lower()}) is {SIGNS[sign]}; its lord {lord} sits in house {lp['house']} "
                 f"({lp['sign']}, {lp['dignity']})"
                 + (f", occupied by {', '.join(occ)}" if occ else ", no occupants")
                 + (f", {bind} Ashtakavarga bindus" if bind is not None else "")
                 + f" → {tone}. "
                 + {"strong": f"This area works for you — lean into it ({theme}).",
                    "average": f"Mixed — use it selectively and with rules ({theme}).",
                    "weak": f"Weak spot — go light here and protect capital ({theme})."}[tone])
        rows.append({"house": h, "title": title, "theme": theme, "sign": SIGNS[sign], "lord": lord,
                     "lord_house": lp["house"], "lord_sign": lp["sign"], "lord_dignity": lp["dignity"],
                     "occupants": occ, "bindus": bind, "score": score, "tone": tone, "plain": plain})
    return rows


def _fit(weights: Dict[str, float], comp: Dict, hs: Dict[int, float], timing: Dict[str, float]):
    tot, contrib = 0.0, []
    for k, w in weights.items():
        if k.startswith("H"):
            v = hs[int(k[1:])]
            label = f"house {k[1:]}"
        else:
            v = comp[k]["score"] + timing.get(k, 0)
            label = k
        tot += w * v
        contrib.append((label, w * v, v))
    contrib.sort(key=lambda c: -c[1])
    return _clip(tot, 3, 98), contrib


def build_plan(chart: Dict, strengths: Dict, analysis: Dict, dasha, capital: float = 50000.0,
               target_weekly: float = 500.0, monthly_savings: float = 500.0,
               base_return: float = 0.08, now: Optional[datetime] = None) -> Dict:
    positions, lag = chart["positions"], chart["lagna_sign"]
    birth = chart["birth"]
    now = now or datetime.utcnow()
    comp = composite_strength(positions, strengths, analysis)
    sav = (analysis.get("ashtakvarga") or {}).get("sav") or []
    hs = {h: house_strength(h, positions, lag, comp, sav) for h in range(1, 13)}

    cur = dasha.current(now)
    md = cur["mahadasha"]["lord"] if cur.get("mahadasha") else None
    ad = cur["antardasha"]["lord"] if cur.get("antardasha") else None
    timing = {}
    if md:
        timing[md] = timing.get(md, 0) + 6
    if ad:
        timing[ad] = timing.get(ad, 0) + 4

    home = birth.get("place", "")
    def mk(items, kind):
        out = []
        for name, spec in items.items():
            weights = spec[0] if isinstance(spec, tuple) else spec
            fit, contrib = _fit(weights, comp, hs, timing)
            if kind == "market" and name.startswith("India") and "India" in home:
                fit = _clip(fit + 5, 3, 98)  # home-market familiarity / tax / hours
            top = ", ".join(f"{c[0]} ({round(c[2])})" for c in contrib[:2])
            weak = contrib[-1]
            why = (f"Driven by {top}" + (f"; held back by {weak[0]} ({round(weak[2])})" if weak[2] < 45 else "")
                   + (f". {spec[1]}" if isinstance(spec, tuple) and kind == "market" else "") + ".")
            out.append({"name": name, "fit": round(fit), "why": why,
                        "drivers": [c[0] for c in contrib[:3]]})
        out.sort(key=lambda r: -r["fit"])
        return out

    markets = mk(MARKETS, "market")
    sectors = mk(SECTORS, "sector")

    verdict_score = (analysis.get("verdict") or {}).get("score", 55)
    strategies = []
    for key, (label, weights, rng, why) in STRATEGIES.items():
        fit, contrib = _fit(weights, comp, hs, timing)
        if key in ("intraday", "options_buying"):
            fit = fit * 0.85 + (verdict_score - 55) * 0.25  # active styles need trading temperament
            moon = comp["Moon"]["score"]
            if moon < 45:
                fit -= 8
        if key == "quant_astro":
            fit += (verdict_score - 55) * 0.15
        fit = _clip(fit, 3, 98)
        strategies.append({"key": key, "label": label, "fit": round(fit), "returns": dict(zip(("low", "base", "high"), rng)),
                           "why": f"{why}. Your drivers: " + ", ".join(f"{c[0]} ({round(c[2])})" for c in contrib[:3]) + "."})
    strategies.sort(key=lambda r: -r["fit"])

    # ── dasha factor: strength of current MD/AD lords (0.85–1.15) ──
    def lord_mod(l1: Optional[str], l2: Optional[str]) -> float:
        if not l1:
            return 1.0
        s = 0.6 * comp[l1]["score"] + 0.4 * comp[l2 or l1]["score"]
        return 0.85 + 0.3 * s / 100.0
    dfac = round(lord_mod(md, ad), 3)

    # ── income bands per strategy (top 4 by fit) ──
    income_rows = []
    for st in strategies[:4]:
        r = st["returns"]
        def scale(x):  # dasha factor amplifies gains, not losses
            return x * dfac if x > 0 else x
        ann = {k: capital * scale(v) for k, v in r.items()}
        base = scale(r["base"])
        need = round(target_weekly * 52 / base) if base > 0.005 else None
        income_rows.append({
            "strategy": st["label"], "key": st["key"], "fit": st["fit"],
            "annual_return_pct": {k: round(scale(v) * 100, 1) for k, v in r.items()},
            "weekly": {k: round(v / 52) for k, v in ann.items()},
            "monthly": {k: round(v / 12) for k, v in ann.items()},
            "yearly": {k: round(v) for k, v in ann.items()},
            "capital_for_target": need,
        })
    primary = income_rows[0]
    if primary["capital_for_target"]:
        tgt_line = (f"To make £{target_weekly:,.0f}/week with {primary['strategy'].lower()} at its base-case "
                    f"{primary['annual_return_pct']['base']}%/yr you'd need roughly £{primary['capital_for_target']:,.0f} of capital"
                    + (" — you have enough." if capital >= primary["capital_for_target"] else
                       f" — about £{primary['capital_for_target'] - capital:,.0f} more than today's £{capital:,.0f}."))
    else:
        tgt_line = f"{primary['strategy']} has no positive base-case return, so no capital level reliably makes £{target_weekly:,.0f}/week."

    # ── lifetime projection ──
    life = lifetime_projection(dasha, comp, birth, now, capital, monthly_savings, base_return)

    top_m, top_s, top_st = markets[0], sectors[:3], strategies[0]
    summary = (f"Focus: {top_m['name']} (fit {top_m['fit']}) · sectors {', '.join(s['name'].split(' (')[0] for s in top_s)} · "
               f"strategy {top_st['label']} (fit {top_st['fit']}). Current {md}/{ad} dasha factor ×{dfac:.2f}. "
               f"{tgt_line}")
    return {
        "composite_strength": comp,
        "wealth_houses": wealth_houses(positions, lag, comp, sav),
        "house_strength": {h: round(v) for h, v in hs.items()},
        "markets": markets, "sectors": sectors, "strategies": strategies,
        "dasha_factor": dfac, "dasha_now": {"md": md, "ad": ad},
        "income": {"capital": capital, "target_weekly": target_weekly, "rows": income_rows,
                   "target_line": tgt_line,
                   "method": ("Bands = capital × each strategy's broad long-run annual return range (low/base/high), "
                              f"with gains scaled by your current dasha factor ×{dfac:.2f}. Weekly = yearly/52, monthly = yearly/12. "
                              "Ranges are reference figures (equities ≈ 7–10%/yr long-run, gilts/bonds 3–5%, studies show most "
                              "retail day-traders and option buyers lose money) — illustrative, never guaranteed.")},
        "lifetime": life,
        "summary": summary,
        "disclaimer": "Educational astrology-based framing, not financial advice. All £ figures are illustrative.",
    }


def lifetime_projection(dasha, comp: Dict, birth: Dict, now: datetime, capital: float,
                        monthly_savings: float, base_return: float, retire_age: int = 60,
                        end_age: int = 85) -> Dict:
    """Year-by-year £ projection from the current age to ``end_age`` (low/base/high)."""
    bdt = datetime.fromisoformat(birth["utc"]) if birth.get("utc") else dasha.birth
    age_now = (now - bdt).days / YEAR
    rows, w = [], {"low": float(capital), "base": float(capital), "high": float(capital)}
    spread = {"low": -0.025, "base": 0.0, "high": 0.025}
    yrs = max(1, int(math.ceil(end_age - age_now)))
    for i in range(yrs + 1):
        t = now + timedelta(days=i * YEAR)
        age = age_now + i
        cur = dasha.current(t)
        md = cur["mahadasha"]["lord"] if cur.get("mahadasha") else None
        ad = cur["antardasha"]["lord"] if cur.get("antardasha") else None
        if md:
            s = 0.6 * comp[md]["score"] + 0.4 * comp[ad or md]["score"]
            mod = 0.8 + 0.4 * s / 100.0
        else:
            mod = 1.0
        rows.append({"age": round(age, 1), "year": t.year, "md": md, "ad": ad, "dasha_mod": round(mod, 3),
                     **{k: round(v) for k, v in w.items()}})
        if i == yrs:
            break
        contrib = 12 * monthly_savings * (1.03 ** i) if age < retire_age else 0.0
        for k in w:
            r = base_return * mod + spread[k]
            w[k] = max(0.0, w[k] * (1 + r) + contrib * (1 + r / 2))
    milestones = []
    for target in (30, 40, 50, 60, 70, 85):
        if target >= age_now:
            row = min(rows, key=lambda r: abs(r["age"] - target))
            milestones.append({"age": target, **{k: row[k] for k in ("year", "md", "low", "base", "high")}})
    # best / worst dasha stretches for compounding
    best = max(rows, key=lambda r: r["dasha_mod"]) if rows else None
    worst = min(rows, key=lambda r: r["dasha_mod"]) if rows else None
    end = rows[-1] if rows else None
    plain = (f"Starting at age {age_now:.0f} with £{capital:,.0f}, saving £{monthly_savings:,.0f}/month (rising 3%/yr until "
             f"age {retire_age}) at a {base_return*100:.1f}% base return modulated by your dasha sequence, the illustrative "
             f"base case reaches about £{end['base']:,.0f} by age {end_age} (range £{end['low']:,.0f}–£{end['high']:,.0f}). "
             f"Strongest compounding years: {best['md']}/{best['ad']} around age {best['age']:.0f}; weakest: "
             f"{worst['md']}/{worst['ad']} around age {worst['age']:.0f} — keep risk low then.") if end else ""
    return {"age_now": round(age_now, 1), "inputs": {"capital": capital, "monthly_savings": monthly_savings,
                                                     "base_return": base_return, "retire_age": retire_age,
                                                     "end_age": end_age},
            "rows": rows, "milestones": milestones, "plain": plain,
            "method": ("Each year: wealth × (1 + base return × dasha modifier ± 2.5 points for the high/low band) + savings. "
                       "Dasha modifier 0.8–1.2 comes from the composite strength of the running mahadasha (60%) and "
                       "antardasha (40%) lords. Nominal £ (not inflation-adjusted); no withdrawals or tax are modelled. Illustrative, not a prediction.")}
