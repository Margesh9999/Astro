"""
Jataka (birth chart) engine — configurable native, market recommendations,
income forecasting, lifetime wealth phases and the final synthesis.

Covers:
  T4  — jataka is configurable AND correlated with the selected stock
  T12 — deep astro analysis, recommended markets/sectors/strategies,
        rough weekly/monthly/annual income, lifetime wealth prediction,
        configurable birth place, default Vedic mode
  T13 — final synthesis: natal placements + today's transits + 30/60/90-day
        and 1-year plan for a stable income from the selected stock
"""
import swisseph as swe
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import math

from app.core.vedic import VedicCalculator
from app.services.dasha import VimshottariDasha, LORD_THEMES, DASHA_INTERPRETATIONS
from app.services.astro_analysis import AstroAnalysis

logger = logging.getLogger(__name__)

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

# ---------------------------------------------------------------------------
# Birth-place gazetteer (queryable via /jataka/places)
# ---------------------------------------------------------------------------
PLACES: List[Dict] = [
    {"name": "Vallabh Vidyanagar, Gujarat, India", "lat": 22.5347, "lon": 73.13, "tz": 5.5},
    {"name": "Ahmedabad, India", "lat": 23.0225, "lon": 72.5714, "tz": 5.5},
    {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777, "tz": 5.5},
    {"name": "Delhi, India", "lat": 28.6139, "lon": 77.2090, "tz": 5.5},
    {"name": "Surat, India", "lat": 21.1702, "lon": 72.8311, "tz": 5.5},
    {"name": "Vadodara, India", "lat": 22.3072, "lon": 73.1812, "tz": 5.5},
    {"name": "Rajkot, India", "lat": 22.3039, "lon": 70.8022, "tz": 5.5},
    {"name": "Pune, India", "lat": 18.5204, "lon": 73.8567, "tz": 5.5},
    {"name": "Bengaluru, India", "lat": 12.9716, "lon": 77.5946, "tz": 5.5},
    {"name": "Chennai, India", "lat": 13.0827, "lon": 80.2707, "tz": 5.5},
    {"name": "Hyderabad, India", "lat": 17.3850, "lon": 78.4867, "tz": 5.5},
    {"name": "Kolkata, India", "lat": 22.5726, "lon": 88.3639, "tz": 5.5},
    {"name": "Jaipur, India", "lat": 26.9124, "lon": 75.7873, "tz": 5.5},
    {"name": "Ujjain, India", "lat": 23.1793, "lon": 75.7849, "tz": 5.5},
    {"name": "Varanasi, India", "lat": 25.3176, "lon": 82.9739, "tz": 5.5},
    {"name": "London, United Kingdom", "lat": 51.5074, "lon": -0.1278, "tz": 0.0},
    {"name": "Manchester, United Kingdom", "lat": 53.4808, "lon": -2.2426, "tz": 0.0},
    {"name": "Birmingham, United Kingdom", "lat": 52.4862, "lon": -1.8904, "tz": 0.0},
    {"name": "Edinburgh, United Kingdom", "lat": 55.9533, "lon": -3.1883, "tz": 0.0},
    {"name": "Leicester, United Kingdom", "lat": 52.6369, "lon": -1.1398, "tz": 0.0},
    {"name": "New York, USA", "lat": 40.7128, "lon": -74.0060, "tz": -5.0},
    {"name": "San Francisco, USA", "lat": 37.7749, "lon": -122.4194, "tz": -8.0},
    {"name": "Chicago, USA", "lat": 41.8781, "lon": -87.6298, "tz": -6.0},
    {"name": "Houston, USA", "lat": 29.7604, "lon": -95.3698, "tz": -6.0},
    {"name": "Los Angeles, USA", "lat": 34.0522, "lon": -118.2437, "tz": -8.0},
    {"name": "Toronto, Canada", "lat": 43.6532, "lon": -79.3832, "tz": -5.0},
    {"name": "Dubai, UAE", "lat": 25.2048, "lon": 55.2708, "tz": 4.0},
    {"name": "Singapore", "lat": 1.3521, "lon": 103.8198, "tz": 8.0},
    {"name": "Hong Kong", "lat": 22.3193, "lon": 114.1694, "tz": 8.0},
    {"name": "Tokyo, Japan", "lat": 35.6762, "lon": 139.6503, "tz": 9.0},
    {"name": "Sydney, Australia", "lat": -33.8688, "lon": 151.2093, "tz": 10.0},
    {"name": "Frankfurt, Germany", "lat": 50.1109, "lon": 8.6821, "tz": 1.0},
    {"name": "Paris, France", "lat": 48.8566, "lon": 2.3522, "tz": 1.0},
    {"name": "Zurich, Switzerland", "lat": 47.3769, "lon": 8.5417, "tz": 1.0},
    {"name": "Johannesburg, South Africa", "lat": -26.2041, "lon": 28.0473, "tz": 2.0},
    {"name": "Nairobi, Kenya", "lat": -1.2921, "lon": 36.8219, "tz": 3.0},
]

# ---------------------------------------------------------------------------
# Classical planetary dignities
# ---------------------------------------------------------------------------
OWN_SIGNS = {
    "Sun": [4], "Moon": [3], "Mercury": [2, 5], "Venus": [1, 6],
    "Mars": [0, 7], "Jupiter": [8, 11], "Saturn": [9, 10], "Rahu": [10], "Ketu": [7],
}
EXALT_SIGN = {"Sun": 0, "Moon": 1, "Mercury": 5, "Venus": 11, "Mars": 9,
              "Jupiter": 3, "Saturn": 6, "Rahu": 1, "Ketu": 7}
DEBIL_SIGN = {k: (v + 6) % 12 for k, v in EXALT_SIGN.items()}
MOOLATRIKONA = {"Sun": 4, "Moon": 1, "Mercury": 5, "Jupiter": 8, "Venus": 6, "Mars": 0, "Saturn": 10}

# houses (1-indexed)
KENDRA = {1, 4, 7, 10}
TRIKONA = {1, 5, 9}
DUSTHANA = {6, 8, 12}

HOUSE_MEANINGS = {
    1: "self, body, first impressions", 2: "savings, speech, family wealth",
    3: "communication, courage, siblings", 4: "home, property, emotional base",
    5: "speculation, children, creativity", 6: "service, debt, health routines",
    7: "partnerships, contracts, the public", 8: "other people's money, insurance, research",
    9: "fortune, higher learning, long journeys", 10: "career, status, public action",
    11: "gains, network, income streams", 12: "foreign lands, expenses, letting go",
}

PLANET_MARKETS = {
    "Sun": {"market": "India & US large-cap", "sectors": ["Government/PSU", "Energy", "Gold", "Capital goods"],
            "note": "authority-backed and energy-linked assets do best in Sun periods"},
    "Moon": {"market": "Global consumer markets", "sectors": ["FMCG", "Pharma", "Dairy", "Hospitality", "Silver"],
             "note": "crowd-mood and liquidity-sensitive consumer names lead"},
    "Mercury": {"market": "US NASDAQ & India IT", "sectors": ["Information technology", "Telecom", "Media", "Logistics", "EdTech"],
                "note": "fast, analytical, trade-heavy businesses flourish"},
    "Jupiter": {"market": "India & US financials", "sectors": ["Banking", "Insurance", "Asset management", "Education", "Gold"],
                "note": "expansion through disciplined financial compounds"},
    "Venus": {"market": "UK & Europe luxury/finance", "sectors": ["Luxury goods", "Automobiles", "Entertainment", "Textiles", "Financial services"],
              "note": "comfort-demand and finance brands accumulate steadily"},
    "Mars": {"market": "Commodity-linked markets", "sectors": ["Energy", "Metals & mining", "Defence", "Real estate", "Cement"],
             "note": "momentum and hard-asset cyclicality reward decisive action"},
    "Saturn": {"market": "UK FTSE value & global infrastructure", "sectors": ["Infrastructure", "Cement", "Mining", "Oil & gas services", "BFSI"],
               "note": "slow, systematic accumulation in disciplined sectors"},
    "Rahu": {"market": "US tech & global innovation", "sectors": ["Software/AI", "Semiconductors", "EV & new mobility", "Crypto-adjacent", "Foreign listings"],
             "note": "speculative innovation waves — ride with strict stops"},
    "Ketu": {"market": "Niche & research themes", "sectors": ["Pharma research", "Spiritual/wellness", "Specialty technology"],
             "note": "simplify holdings; niche expertise beats breadth"},
}

STRATEGY_PROFILES = {
    "institutional_quant": {
        "label": "Institutional quant astro trading",
        "desc": "systematic, model-driven positions reviewed daily — your analytical grahas dominate",
        "yield": (0.12, 0.22, 0.30), "profile": ["Mercury", "Jupiter", "Saturn"],
    },
    "swing_equity": {
        "label": "Swing equity trading (5–20 day holds)",
        "desc": "ride 1–4 week momentum waves with defined entries and exits",
        "yield": (0.15, 0.25, 0.40), "profile": ["Mars", "Rahu", "Sun"],
    },
    "options_income": {
        "label": "Options income (credit spreads & covered calls)",
        "desc": "weekly premium harvesting with defined-risk structures",
        "yield": (0.10, 0.18, 0.28), "profile": ["Mercury", "Venus", "Ketu"],
    },
    "long_term_equity": {
        "label": "Long-term equity accumulation",
        "desc": "quality compounders bought on dips, held for years",
        "yield": (0.08, 0.14, 0.20), "profile": ["Jupiter", "Venus", "Moon"],
    },
    "fixed_income": {
        "label": "Fixed income & systematic accumulation",
        "desc": "bonds, deposits and disciplined DCA into indices",
        "yield": (0.05, 0.09, 0.13), "profile": ["Saturn", "Moon"],
    },
}

WEALTH_NATURE = {  # dasha-lord wealth potential 0..1
    "Jupiter": 0.95, "Venus": 0.90, "Mercury": 0.85, "Moon": 0.70, "Sun": 0.70,
    "Mars": 0.65, "Saturn": 0.75, "Rahu": 0.60, "Ketu": 0.40,
}

BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
MALEFICS = {"Saturn", "Mars", "Rahu", "Ketu", "Sun"}


def _dignity(name: str, sign: int, deg: float) -> Tuple[str, float]:
    """Return (dignity_label, score 0..1)."""
    if name in ("Lagna",):
        return ("reference", 0.5)
    if EXALT_SIGN.get(name) == sign:
        return ("exalted", 1.0)
    if DEBIL_SIGN.get(name) == sign:
        return ("debilitated", 0.15)
    if name in MOOLATRIKONA and MOOLATRIKONA[name] == sign and deg <= 20:
        return ("moolatrikona", 0.9)
    if sign in OWN_SIGNS.get(name, []):
        return ("own sign", 0.75)
    if name in ("Rahu", "Ketu"):
        return ("neutral node", 0.45)
    # friendly sign heuristic: signs owned by natural friends
    FRIENDS = {
        "Sun": [8, 9], "Moon": [11, 4], "Mercury": [1, 6, 10, 11], "Venus": [2, 3, 9, 10],
        "Mars": [8, 9, 4], "Jupiter": [0, 7, 9], "Saturn": [2, 5, 6],
    }
    if sign in FRIENDS.get(name, []):
        return ("friendly sign", 0.55)
    return ("neutral", 0.4)


class JatakaEngine:
    """Configurable Vedic birth-chart engine with market & income guidance."""

    def __init__(self, ayanamsa_mode: int = swe.SIDM_LAHIRI):
        self.vedic = VedicCalculator(ayanamsa_mode=ayanamsa_mode)
        self.default_birth = {
            "name": "Margesh",
            "date": "1994-04-23", "time": "06:45",
            "place": "Vallabh Vidyanagar, Gujarat, India",
            "lat": 22.5347, "lon": 73.13, "tz": 5.5,
        }

    # ------------------------------------------------------------------
    def search_places(self, q: str) -> List[Dict]:
        ql = (q or "").strip().lower()
        if not ql:
            return PLACES[:10]
        starts = [p for p in PLACES if p["name"].lower().startswith(ql)]
        contains = [p for p in PLACES if ql in p["name"].lower() and p not in starts]
        return (starts + contains)[:10]

    def _resolve_place(self, place: str) -> Dict:
        for p in PLACES:
            if p["name"].lower() == (place or "").lower():
                return p
        hits = self.search_places(place or "")
        return hits[0] if hits else {"name": place or "Ujjain, India", "lat": 23.1793, "lon": 75.7849, "tz": 5.5}

    # ------------------------------------------------------------------
    def compute_chart(self, name: str = "", date: str = "", time: str = "",
                      place: str = "", lat: Optional[float] = None,
                      lon: Optional[float] = None, tz: Optional[float] = None) -> Dict:
        """Full sidereal chart for ANY configurable birth data."""
        b = {**self.default_birth, "name": name or "Native", "date": date or self.default_birth["date"],
             "time": time or self.default_birth["time"], "place": place or self.default_birth["place"]}
        p = self._resolve_place(b["place"])
        if lat is not None: p["lat"] = lat
        if lon is not None: p["lon"] = lon
        if tz is not None: p["tz"] = tz
        # adopt resolved coordinates WITHOUT clobbering the native's name
        # (place dicts carry their own "name" key — the old b.update(p) erased it)
        b["place"] = p["name"]
        b["lat"], b["lon"], b["tz"] = p["lat"], p["lon"], p["tz"]

        y, m, d = [int(x) for x in b["date"].split("-")]
        hh, mm = [int(x) for x in b["time"].split(":")]
        local = datetime(y, m, d, hh, mm)
        utc_dt = local - timedelta(hours=b["tz"])
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                        utc_dt.hour + utc_dt.minute / 60.0)
        swe.set_sid_mode(swe.SIDM_LAHIRI)

        grahas = {"Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
                  "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}
        positions = {}
        for gname, pid in grahas.items():
            data = self.vedic.calculate_planet_position_vedic(pid, jd)
            positions[gname] = data
            if gname == "Rahu":
                klon = (data["longitude"] + 180) % 360
                nak = self.vedic.calculate_nakshatra(klon)
                positions["Ketu"] = {
                    "longitude": klon, "sign": SIGNS[int(klon // 30)],
                    "sign_number": int(klon // 30), "degree_within_sign": klon % 30,
                    "is_retrograde": True, "nakshatra": nak["nakshatra"],
                    "nakshatra_index": nak["nakshatra_index"], "pada": nak["pada"],
                }
        cusps, ascmc = swe.houses_ex(jd, p["lat"], p["lon"], b'W', flags=swe.FLG_SIDEREAL)
        asc = ascmc[0] % 360
        anak = self.vedic.calculate_nakshatra(asc)
        positions["Lagna"] = {
            "longitude": asc, "sign": SIGNS[int(asc // 30)], "sign_number": int(asc // 30),
            "degree_within_sign": asc % 30, "is_retrograde": False,
            "nakshatra": anak["nakshatra"], "nakshatra_index": anak["nakshatra_index"], "pada": anak["pada"],
        }
        lagna_sign = int(asc // 30)
        for _, pos in positions.items():
            sn = pos.get("sign_number", int(pos["longitude"] // 30))
            pos["house"] = (sn - lagna_sign) % 12 + 1
            pos["dignity"], pos["dignity_score"] = _dignity(_, sn, pos.get("degree_within_sign", 0))

        moon = positions["Moon"]
        dasha = VimshottariDasha(moon["longitude"], utc_dt)
        return {
            "birth": {"name": b["name"], "date": b["date"], "time": b["time"],
                      "place": p["name"], "lat": p["lat"], "lon": p["lon"], "tz": p["tz"],
                      "utc": utc_dt.isoformat()},
            "ayanamsa_mode": "Lahiri (Chitrapaksha)",
            "ayanamsa": round(swe.get_ayanamsa_ut(jd), 4),
            "jd": jd,
            "positions": positions,
            "lagna_sign": lagna_sign,
            "dasha": dasha,
        }

    # ------------------------------------------------------------------
    def strengths(self, positions: Dict) -> Dict:
        """Score each graha 0..100 for trading-relevant strength."""
        scores, notes = {}, {}
        for g, pos in positions.items():
            if g == "Lagna":
                continue
            s = pos["dignity_score"] * 55
            h = pos.get("house", 1)
            if h in KENDRA: s += 20
            if h in TRIKONA: s += 18
            if h in DUSTHANA: s -= 12
            if h in (2, 11): s += 12  # wealth & gains houses
            if pos.get("is_retrograde") and g not in ("Rahu", "Ketu"): s -= 4
            notes[g] = (
                f"{g} in {pos['sign']} (house {h}, {pos['dignity']}) — "
                f"touches {HOUSE_MEANINGS[h]}"
            )
            scores[g] = max(2, min(100, round(s)))
        order = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return {"scores": scores, "notes": notes, "ranked": order}

    def _dasha_favour(self, lord: str) -> float:
        if lord in BENEFICS: return 1.15
        if lord == "Mercury": return 1.20
        if lord in ("Saturn", "Sun"): return 0.95
        if lord == "Mars": return 0.90
        if lord == "Rahu": return 0.85
        if lord == "Ketu": return 0.70
        return 1.0

    # ------------------------------------------------------------------
    def market_recommendations(self, positions: Dict, strengths: Dict) -> Dict:
        """Recommended markets / sectors / strategies from planetary strength (T12②)."""
        ranked = strengths["ranked"][:5]
        top = [g for g, _ in ranked]
        # market votes
        votes: Dict[str, float] = {}
        for g in top:
            w = strengths["scores"][g] / 100.0
            mkt = PLANET_MARKETS[g]["market"]
            votes[mkt] = votes.get(mkt, 0) + w
        markets = sorted(votes.items(), key=lambda kv: kv[1], reverse=True)
        total = sum(v for _, v in markets) or 1.0
        allocation = [{"market": m, "weight_pct": round(100 * v / total), "driven_by": ", ".join(
            [g for g in top if PLANET_MARKETS[g]["market"] == m])} for m, v in markets[:4]]

        # sector votes
        svotes: Dict[str, float] = {}
        for g in top:
            w = strengths["scores"][g] / 100.0
            for sec in PLANET_MARKETS[g]["sectors"]:
                svotes[sec] = svotes.get(sec, 0) + w
        sectors = sorted(svotes.items(), key=lambda kv: kv[1], reverse=True)[:8]
        sv_total = sum(v for _, v in sectors) or 1.0

        # strategy match
        strat_scores = {}
        for key, prof in STRATEGY_PROFILES.items():
            sc = sum(strengths["scores"].get(g, 0) for g in prof["profile"])
            strat_scores[key] = sc
        best = sorted(strat_scores.items(), key=lambda kv: kv[1], reverse=True)
        lagna_lord_sign = None  # not needed for now
        strategies = [{
            "key": k,
            "label": STRATEGY_PROFILES[k]["label"],
            "desc": STRATEGY_PROFILES[k]["desc"],
            "fit_score": round(s / max(1, best[0][1]) * 100),
        } for k, s in best[:3]]

        return {
            "allocation": allocation,
            "sectors": [{"sector": s, "weight_pct": round(100 * v / sv_total)} for s, v in sectors],
            "strategies": strategies,
            "rationale": (
                f"Your strongest grahas are {top[0]}, {top[1]} and {top[2]}. "
                f"{PLANET_MARKETS[top[0]]['note'].capitalize()}, while {PLANET_MARKETS[top[1]]['note']} "
                f"This combination points to {strategies[0]['label']} as the primary approach."
            ),
        }

    # ------------------------------------------------------------------
    def income_forecast(self, positions: Dict, strengths: Dict, dasha: VimshottariDasha,
                        capital: float = 50000.0, target_weekly: float = 500.0) -> Dict:
        """Rough weekly / monthly / annual income bands (T12③)."""
        strat = self.market_recommendations(positions, strengths)["strategies"][0]
        lo, mid, hi = STRATEGY_PROFILES[strat["key"]]["yield"]
        cur = dasha.current()
        fav = self._dasha_favour(cur["mahadasha"]["lord"]) if cur["mahadasha"] else 1.0
        lo_a, mid_a, hi_a = lo * capital * fav, mid * capital * fav, hi * capital * fav
        weekly = {"low": round(lo_a / 52, 2), "mid": round(mid_a / 52, 2), "high": round(hi_a / 52, 2)}
        monthly = {"low": round(lo_a / 12, 2), "mid": round(mid_a / 12, 2), "high": round(hi_a / 12, 2)}
        annual = {"low": round(lo_a, 2), "mid": round(mid_a, 2), "high": round(hi_a, 2)}
        # target feasibility
        need_mid = target_weekly * 52 / max(0.06, mid)
        need_low = target_weekly * 52 / max(0.06, lo)
        return {
            "strategy": strat["label"],
            "capital": capital,
            "dasha_factor": fav,
            "weekly": weekly, "monthly": monthly, "annual": annual,
            "target_weekly": target_weekly,
            "target_feasible": capital >= need_mid,
            "target_capital_needed": {"at_mid_yield": round(need_mid), "at_low_yield": round(need_low)},
            "honesty": (
                f"These are modelled bands from the {strat['label']} playbook at £{capital:,.0f} capital, "
                f"scaled by your {cur['mahadasha']['lord'] if cur['mahadasha'] else '-'} dasha factor ×{fav:.2f}. "
                f"Reaching £{target_weekly:,.0f}/week needs roughly £{need_mid:,.0f} at the mid yield "
                f"(£{need_low:,.0f} if only the low yield materialises). Premium capture is not profit; "
                f"drawdowns are part of every band shown."
            ),
        }

    # ------------------------------------------------------------------
    def lifetime_wealth(self, dasha: VimshottariDasha) -> Dict:
        """Wealth-accumulation prediction across life stages (T12④)."""
        stages = []
        birth = dasha.birth
        for md in dasha.tree:
            age_start = (md["start"] - birth).days / 365.2425
            age_end = (md["end"] - birth).days / 365.2425
            mid_age = (age_start + age_end) / 2
            # age factor
            if mid_age < 18: age_f = 0.30
            elif mid_age < 30: age_f = 0.60
            elif mid_age < 45: age_f = 1.00
            elif mid_age < 58: age_f = 1.10
            elif mid_age < 70: age_f = 0.80
            else: age_f = 0.60
            base = WEALTH_NATURE[md["lord"]]
            favour = self._dasha_favour(md["lord"])
            score = max(5, min(100, round(base * age_f * favour * 90)))
            phase = ("Foundation years" if mid_age < 18 else
                     "Learning & first earnings" if mid_age < 30 else
                     "Wealth accumulation peak" if mid_age < 45 else
                     "Compounding & leadership years" if mid_age < 58 else
                     "Preservation & distribution" if mid_age < 70 else "Legacy years")
            stages.append({
                "lord": md["lord"], "age_from": round(age_start, 1), "age_to": round(age_end, 1),
                "start": md["start"].strftime("%Y"), "end": md["end"].strftime("%Y"),
                "wealth_index": score, "phase": phase,
                "note": (f"{md['lord']} years ({md['start'].strftime('%Y')}–{md['end'].strftime('%Y')}): "
                         f"{DASHA_INTERPRETATIONS[md['lord']]}"),
            })
        peak = max(stages, key=lambda s: s["wealth_index"])
        return {
            "stages": stages,
            "peak": peak,
            "headline": (f"Your strongest wealth window is the {peak['lord']} dasha "
                         f"(age {peak['age_from']}–{peak['age_to']}, {peak['start']}–{peak['end']})."),
        }

    # ------------------------------------------------------------------
    def transits_today(self, positions: Dict) -> Dict:
        """Today's planetary positions vs natal — conjunctions to natal grahas."""
        now = datetime.utcnow()
        jd = swe.julday(now.year, now.month, now.day, now.hour / 24.0)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        transits = {}
        for g, pid in {"Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
                       "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
                       "Rahu": swe.MEAN_NODE}.items():
            data = self.vedic.calculate_planet_position_vedic(pid, jd)
            transits[g] = data
        hits = []
        for tg, tpos in transits.items():
            for ng, npos in positions.items():
                if ng == "Lagna": continue
                sep = abs((tpos["longitude"] - npos["longitude"] + 180) % 360 - 180)
                if sep <= 8:
                    hits.append({"transit": tg, "natal": ng, "separation": round(sep, 1),
                                 "meaning": (f"Transiting {tg} sits on your natal {ng} — "
                                             f"{LORD_THEMES[tg].split(';')[0]} themes activate today.")})
        return {"transits": {g: {"sign": t["sign"], "degree": round(t["degree_within_sign"], 1),
                                 "nakshatra": t["nakshatra"]} for g, t in transits.items()},
                "activations": hits}

    # ------------------------------------------------------------------
    def synthesis(self, positions: Dict, strengths: Dict, dasha: VimshottariDasha,
                  symbol: str, symbol_name: str, capital: float = 50000.0,
                  target_weekly: float = 500.0) -> Dict:
        """T13 — natal planets + today's transits + 30/60/90-day & 1-year plan for the stock."""
        recs = self.market_recommendations(positions, strengths)
        inc = self.income_forecast(positions, strengths, dasha, capital, target_weekly)
        trans = self.transits_today(positions)
        interp = dasha.interpretation()
        top = [g for g, _ in strengths["ranked"][:3]]
        cur = dasha.current()

        def window(days: int, label: str) -> Dict:
            return {
                "window": label,
                "action": (
                    f"Over the next {days} days, trade {symbol_name} ({symbol}) in the direction the "
                    f"{interp['headline']} permits: favour {recs['sectors'][0]['sector']} exposure on dips, "
                    f"size positions at ≤{(8 if top[0] in MALEFICS else 12)}% of capital per trade, and let the "
                    f"{cur['antardasha']['lord'] if cur['antardasha'] else '-'} sub-period "
                    f"({LORD_THEMES[cur['antardasha']['lord']].split(';')[0] if cur['antardasha'] else 'current'}) "
                    f"set the pace — {'' if top[0] not in MALEFICS else 'keep stops tight because '}"
                    f"{top[0]} energy rewards {'decisiveness with discipline' if top[0] in MALEFICS else 'patient accumulation'}."
                ),
            }

        plan = [window(30, "Next 30 days"), window(60, "Next 60 days"), window(90, "Next 90 days"),
                window(365, "Next 12 months")]
        return {
            "natal_headline": (f"Lagna {positions['Lagna']['sign']}, Moon in {positions['Moon']['sign']} "
                               f"({positions['Moon']['nakshatra']} pada {positions['Moon']['pada']}), "
                               f"strongest grahas {', '.join(top)}."),
            "current_dasha": interp,
            "transit_activations": trans["activations"][:5],
            "market_fit": recs,
            "income": inc,
            "plan": plan,
            "bottom_line": (
                f"For {symbol_name}, your chart favours a {'risk-aware, stop-disciplined' if top[0] in MALEFICS else 'patient, accumulate-on-weakness'} "
                f"approach inside {recs['allocation'][0]['market']}. Combine the {inc['strategy'].lower()} playbook "
                f"with the dasha timing above; review at every antardasha change."
            ),
        }

    # ------------------------------------------------------------------
    def full_report(self, symbol: str = "^GSPC", symbol_name: str = "S&P 500",
                    capital: float = 50000.0, target_weekly: float = 500.0, **kwargs) -> Dict:
        chart = self.compute_chart(**kwargs)
        positions = chart["positions"]
        dasha = chart["dasha"]
        strengths = self.strengths(positions)
        cur = dasha.current()
        def ser_md(md):
            return {"lord": md["lord"], "glyph": md["glyph"],
                    "start": md["start"].strftime("%d-%m-%Y"), "end": md["end"].strftime("%d-%m-%Y"),
                    "years": md["years"],
                    "antardashas": [{"lord": a["lord"], "glyph": a["glyph"],
                                     "start": a["start"].strftime("%d-%m-%Y"),
                                     "end": a["end"].strftime("%d-%m-%Y"), "years": a["years"]} for a in md["antardashas"]]}
        market_recs = self.market_recommendations(positions, strengths)
        income = self.income_forecast(positions, strengths, dasha, capital, target_weekly)
        # Astro Analysis master guide engine (BPHS + Jaimini + Nakshatra/KV +
        # Shadbala/Bhavabala/Ashtakvarga + KP + Yogini + Money Blueprint)
        try:
            analysis = AstroAnalysis(ayanamsa_mode=swe.SIDM_LAHIRI).build(
                chart, dasha, strengths, market_recs, income, symbol, symbol_name)
        except Exception as exc:  # never let the analysis pack break the report
            logger.exception("astro analysis build failed: %s", exc)
            analysis = {"error": str(exc)}
        return {
            "success": True,
            "birth": chart["birth"],
            "ayanamsa_mode": chart["ayanamsa_mode"],
            "ayanamsa": chart.get("ayanamsa"),
            "lagna_sign": chart["lagna_sign"],
            "positions": positions,
            "strengths": strengths,
            "verdict": analysis.get("verdict"),
            "planetary_notes": analysis.get("planetary_notes"),
            "dasha_tree": {"first_lord": dasha.first_lord,
                           "balance_years": dasha.balance_years,
                           "moon_nakshatra_index": dasha.nak_index,
                           "pada": dasha.pada,
                           "mahadashas": [ser_md(md) for md in dasha.tree]},
            "current_dasha": {
                "mahadasha": cur["mahadasha"]["lord"] if cur["mahadasha"] else None,
                "antardasha": cur["antardasha"]["lord"] if cur["antardasha"] else None,
                "pratyantardasha": cur["pratyantardasha"]["lord"] if cur["pratyantardasha"] else None,
                "md_start": cur["mahadasha"]["start"].strftime("%d-%m-%Y") if cur["mahadasha"] else None,
                "md_end": cur["mahadasha"]["end"].strftime("%d-%m-%Y") if cur["mahadasha"] else None,
                "ad_start": cur["antardasha"]["start"].strftime("%d-%m-%Y") if cur["antardasha"] else None,
                "ad_end": cur["antardasha"]["end"].strftime("%d-%m-%Y") if cur["antardasha"] else None,
                "interpretation": dasha.interpretation(),
            },
            "market_recommendations": market_recs,
            "income_forecast": income,
            "lifetime_wealth": self.lifetime_wealth(dasha),
            "transits_today": self.transits_today(positions),
            "synthesis": self.synthesis(positions, strengths, dasha, symbol, symbol_name,
                                        capital, target_weekly),
            "astro_analysis": analysis,
        }
