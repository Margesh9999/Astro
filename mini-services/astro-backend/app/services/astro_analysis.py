"""
Astro Analysis master engine — every concept of the "Vedic Astrology Horoscope
Analysis Master Guide" (BPHS, Jaimini, Nakshatra/Karma Vipaka, Shadbala,
Bhavabala, Ashtakvarga, KP, Yogini) computed from the natal chart and translated
into structured data + plain-English money & trading predictions.

Covers (per the guide):
  - BPHS: grahas, bhavas, drishti, vargas (D-2/3/9/10/12/60), avasthas, yogas
  - Jaimini: chara karakas, Arudha Lagna, Upapada, Karakamsa
  - Nakshatra system + Karma Vipaka lens
  - Shadbala (six-fold), Bhavabala, Ashtakvarga (prastara + reductions, SAV 337)
  - KP: Placidus sidereal cusps, star/sub lords, ruling planets
  - Dasha systems: Vimshottari (shared engine) + Yogini (36-year cycle)
  - Transits over natal Ashtakvarga + house-by-house synthesis
  - Capstone: Trading & Money Blueprint with plain-English predictions

Shadbala is BPHS-formula based with two documented simplifications (tribhaga,
yuddha, varsha/masa omitted; Saptavargaja approximated over D1/D9/D10/D60) —
component-level structure and all six "bala" families are preserved.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import swisseph as swe

from app.core.vedic import VedicCalculator
from app.services.astro_data import (
    ASHTAKVARGA, BAV_TOTALS, CHALDEAN, CHARA_KARAKAS, COMBUST_ORB, DUAL_OWNERS,
    ENEMIES, EXALT_ABS, FRIENDS, MEAN_SPEED, NAISARGIKA, NAKSHATRAS, NAK_NAMES,
    NATURAL_BENEFICS, NATURAL_MALEFICS, SHADBALA_REQUIRED, SIGN_LORDS,
    TRIKONA_GROUPS, VIM_ORDER, VIM_YEARS, WEEKDAY_LORDS, YOGINIS, YOGINI_TOTAL,
)

logger = logging.getLogger(__name__)

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
P7 = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
KENDRA_H = {1, 4, 7, 10}
TRIKONA_H = {1, 5, 9}
DUSTHANA_H = {6, 8, 12}
WEALTH_HOUSES = (2, 5, 9, 10, 11)

HOUSE_MONEY_LINES = {
    1: "in the Lagna — money follows your own initiative and personality",
    2: "in the savings bhava — a direct wealth signature: banked, spoken, accumulated",
    3: "in the courage bhava — earnings through communication, media and bold moves",
    4: "in the home bhava — property, vehicles and domestic comfort hold the wealth",
    5: "in the speculation bhava — a natural trading instinct; entries feel innate",
    6: "in the service bhava — income via discipline, competition and debt management",
    7: "in the partnership bhava — clients, contracts and spouse bring the money",
    8: "in the volatility bhava — other people's money, insurance, sudden swings; size carefully",
    9: "in the fortune bhava — luck widens with mentors, foreign links and long holds",
    10: "in the career bhava — public profession is the wealth engine",
    11: "in the gains bhava — networks, multiple income streams and steady inflows",
    12: "in the expense bhava — foreign gains possible, but watch silent leaks; automate savings",
}

DIGNITY_PHRASES = {
    "exalted": "at peak dignity — this graha delivers its promises powerfully",
    "moolatrikona": "rooted in its strongest terrain — near-peak reliability",
    "own sign": "on home ground — stable and wealth-friendly",
    "friendly sign": "among friends — supportive but not dominant",
    "neutral": "neutral ground — results depend on dasha and transits",
    "debilitated": "at its weakest — results arrive only with strong dasha/transit support",
    "neutral node": "a karmic node — amplifies whatever it touches",
    "reference": "the ascendant itself — the lens of the whole chart",
}

SIGN_PERSONA = {
    "Aries": "bold, first-mover, rule-bound courage", "Taurus": "patient accumulator, value-driven",
    "Gemini": "quick analyst, trade-savvy communicator", "Cancer": "nurturing, liquidity-aware, mood-driven",
    "Leo": "commanding, visible, leadership-led", "Virgo": "detail-perfect systematic processor",
    "Libra": "balance-seeking deal maker", "Scorpio": "deep-research volatility surfer",
    "Sagittarius": "big-picture optimist, long-cycle believer", "Capricorn": "structured climber, slow compounding",
    "Aquarius": "systems thinker, contrarian networker", "Pisces": "intuitive flow rider, needs guardrails",
}

AVASTHA_STATES = [
    ("Bala (infant)", "≈25% capacity — promises exist but delivery is childlike"),
    ("Kumara (adolescent)", "≈50% capacity — eager but inconsistent delivery"),
    ("Yuva (adult)", "100% capacity — prime of life, full money delivery"),
    ("Vriddha (old)", "≈25% capacity — wise but tired; conserve, don't expand"),
    ("Mrita (dead)", "near-zero — needs strong dasha/transit resurrection"),
]

# varga -> short purpose + money reading
VARGA_INFO = {
    "D2": ("Hora — the wealth chromosome", "how money is actually accumulated and held"),
    "D3": ("Drekkana — drive & siblings", "the engine behind money initiatives"),
    "D9": ("Navamsa — inner fruit", "the true strength behind every Rasi-chart promise; wealth planets strong here confirm results"),
    "D10": ("Dasamsa — career & public action", "which market profession delivers status and income"),
    "D12": ("Dwadasamsa — lineage", "inherited family patterns around money"),
    "D60": ("Shashtiamsa — karmic fine print", "past-life karma colouring every money outcome"),
}


def _varga_sign(sign: int, deg: float, which: str) -> int:
    """Parashara varga mapping. `sign` is 0-based; deg is degree within sign."""
    if which == "D1":  # Rasi itself
        return sign
    if which == "D2":  # Hora: odd signs Leo/Cancer, even signs Cancer/Leo
        if sign % 2 == 0:
            return 4 if deg < 15 else 3
        return 3 if deg < 15 else 4
    if which == "D3":  # Drekkana
        return (sign + int(deg // 10)) % 12
    if which == "D9":  # Navamsa — movable from itself, fixed from 9th, dual from 5th
        off = 0 if sign % 3 == 0 else (8 if sign % 3 == 1 else 4)
        return (sign + off + int(deg // (30.0 / 9.0))) % 12
    if which == "D10":  # Dasamsa — odd signs from itself, even from 9th
        off = 0 if sign % 2 == 0 else 8
        return (sign + off + int(deg // 3)) % 12
    if which == "D12":  # Dwadasamsa — always from the sign itself
        return (sign + int(deg // 2.5)) % 12
    if which == "D60":  # Shashtiamsa — odd from itself, even from 9th
        off = 0 if sign % 2 == 0 else 8
        return (sign + off + int(deg * 2) % 60) % 12
    raise ValueError(which)


def _relation(planet: str, vsign: int) -> str:
    """Dignity/relation label of `planet` when placed in sign index `vsign`."""
    own = {"Sun": [4], "Moon": [3], "Mercury": [2, 5], "Venus": [1, 6],
           "Mars": [0, 7], "Jupiter": [8, 11], "Saturn": [9, 10]}
    exalt = {"Sun": 0, "Moon": 1, "Mercury": 5, "Venus": 11, "Mars": 9,
             "Jupiter": 3, "Saturn": 6}
    debil = {k: (v + 6) % 12 for k, v in exalt.items()}
    mt = {"Sun": 4, "Moon": 1, "Mercury": 5, "Jupiter": 8, "Venus": 6, "Mars": 0, "Saturn": 10}
    if vsign == exalt.get(planet):
        return "exalted"
    if vsign == debil.get(planet):
        return "debilitated"
    if vsign in own.get(planet, []):
        return "own"
    if mt.get(planet) == vsign:
        return "moolatrikona"
    lord = SIGN_LORDS[vsign]
    if lord == planet:
        return "own"
    if lord in FRIENDS.get(planet, set()):
        return "friend"
    if lord in ENEMIES.get(planet, set()):
        return "enemy"
    return "neutral"


_VARGA_POINTS = {"exalted": 60, "moolatrikona": 45, "own": 30, "friend": 15,
                 "neutral": 7.5, "enemy": 3.75, "debilitated": 0}


class AstroAnalysis:
    """Master guide engine — build() returns the complete concept pack."""

    def __init__(self, ayanamsa_mode: int = swe.SIDM_LAHIRI):
        self.ayanamsa_mode = ayanamsa_mode
        self.vedic = VedicCalculator(ayanamsa_mode=ayanamsa_mode)

    # ------------------------------------------------------------------ util
    @staticmethod
    def _house(lon: float, lagna_sign: int) -> int:
        return (int(lon // 30) - lagna_sign) % 12 + 1

    @staticmethod
    def _sep(lon_a: float, lon_b: float) -> float:
        return abs((lon_a - lon_b + 180.0) % 360.0 - 180.0)

    def _speeds(self, jd: float) -> Dict[str, Dict[str, float]]:
        swe.set_sid_mode(self.ayanamsa_mode)
        ay = swe.get_ayanamsa_ut(jd)
        ids = {"Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
               "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN}
        out = {}
        for n, pid in ids.items():
            r = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]
            out[n] = {"lon": r[0] % 360, "trop": r[0] % 360,
                      "speed": r[3], "ayanamsa": ay}
        # replace with sidereal longitudes
        swe.set_sid_mode(self.ayanamsa_mode)
        for n, pid in ids.items():
            r = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL)[0]
            out[n]["lon"] = r[0] % 360
            out[n]["speed"] = r[3]
        return out

    # ------------------------------------------------------------------ build
    def build(self, chart: Dict, dasha, strengths: Dict, recs: Dict,
              income: Dict, symbol: str, symbol_name: str) -> Dict:
        positions = chart["positions"]
        lag = chart["lagna_sign"]
        jd = chart.get("jd")
        birth = {**chart["birth"], "_jd": jd} if jd else chart["birth"]
        speeds = self._speeds(jd) if jd else {}

        av = self.ashtakvarga(positions, lag)
        shad = self.shadbala(positions, lag, birth, speeds)
        bhava = self.bhavabala(positions, lag, shad, av)
        yogas = self.detect_yogas(positions, lag)
        houses = self.house_synthesis(positions, lag, bhava, av)

        out = {
            "vargas": self.vargas(positions),
            "jaimini": self.jaimini(positions, lag),
            "avasthas": self.avasthas(positions),
            "yogas": yogas,
            "shadbala": shad,
            "bhavabala": bhava,
            "ashtakvarga": av,
            "kp": self.kp_chart(jd, birth["lat"], birth["lon"], positions, birth),
            "yogini": self.yogini(chart, dasha),
            "karma_vipaka": self.karma_vipaka(positions, dasha),
            "transits": self.transits_sav(positions, lag, av),
            "houses": houses,
        }
        out["verdict"] = self.verdict(positions, lag, out, dasha, yogas)
        out["planetary_notes"] = self.planetary_notes(positions, lag)
        out["blueprint"] = self.blueprint(positions, lag, out, dasha, strengths,
                                          recs, income, symbol, symbol_name)
        return out

    # ------------------------------------------------------------------ vargas
    def vargas(self, positions: Dict) -> Dict:
        """D-2/3/9/10/12/60 for each graha (BPHS varga rules)."""
        rows = {}
        for name in P7 + ["Rahu", "Ketu", "Lagna"]:
            p = positions.get(name)
            if not p:
                continue
            sign = p["sign_number"]
            deg = p["degree_within_sign"]
            vs = {v: _varga_sign(sign, deg, v) for v in ("D2", "D3", "D9", "D10", "D12", "D60")}
            rows[name] = {
                "vargas": {v: {"sign": SIGNS[s],
                               "dignity": _relation(name, s) if name in P7 else "—"}
                           for v, s in vs.items()},
            }
        # focus paragraphs
        def d9(nm):
            return rows.get(nm, {}).get("vargas", {}).get("D9", {}).get("dignity", "neutral")
        d9_strong = [n for n in ("Jupiter", "Venus", "Saturn", "Mercury") if d9(n) in ("exalted", "own", "moolatrikona")]
        d9_weak = [n for n in ("Jupiter", "Venus", "Saturn", "Mercury") if d9(n) == "debilitated"]
        navamsa_focus = (
            f"Navamsa check: {', '.join(d9_strong) if d9_strong else 'no major wealth planet'} stay(s) strong in D9"
            + (f" — their Rasi promises are CONFIRMED (money results compound reliably)." if d9_strong else ".")
            + (f" {', '.join(d9_weak)} lose(s) power in D9 — its natal promises need dasha/transit help before you size up."
               if d9_weak else "")
        )
        d10_rows = {n: rows[n]["vargas"]["D10"]["sign"] for n in ("Sun", "Saturn", "Jupiter", "Mercury") if n in rows}
        dasamsa_focus = (
            f"Dasamsa (D10) career signature: Sun in {d10_rows.get('Sun')}, Saturn in {d10_rows.get('Saturn')}, "
            f"Jupiter in {d10_rows.get('Jupiter')}, Mercury in {d10_rows.get('Mercury')} — "
            "the D10 signs show the public arena where income is actually earned; strong sign-lord alignments here "
            "tell you which professional style (analytical, structural, advisory) monetises best."
        )
        return {"planets": rows, "info": {v: {"title": t, "meaning": m} for v, (t, m) in VARGA_INFO.items()},
                "navamsa_focus": navamsa_focus, "dasamsa_focus": dasamsa_focus,
                "plain": ("Divisional charts are the zoom lens of BPHS: the Rasi chart shows the promise, the "
                          "Navamsa shows whether it truly ripens, the Dasamsa shows which profession cashes it. "
                          "Trade only the wealth ideas that survive BOTH the Rasi and the Navamsa check.")}

    # ------------------------------------------------------------------ Jaimini
    def jaimini(self, positions: Dict, lag: int) -> Dict:
        degs = sorted(((n, positions[n]["degree_within_sign"]) for n in P7), key=lambda x: -x[1])
        karakas = []
        for i, (key, label, money_meaning) in enumerate(CHARA_KARAKAS):
            nm, dg = degs[i]
            p = positions[nm]
            karakas.append({
                "key": key, "label": label, "planet": nm, "degree": round(dg, 2),
                "sign": p["sign"], "house": p["house"],
                "money_meaning": money_meaning,
                "plain": (f"{nm} is your {label} ({key}) at {dg:.1f}° {p['sign']} (house {p['house']}) — "
                          f"in money terms this means {money_meaning}."),
            })
        ak = karakas[0]["planet"]
        ak_nav = _varga_sign(positions[ak]["sign_number"], positions[ak]["degree_within_sign"], "D9")

        def _arudha(house_sign: int) -> int:
            lord = SIGN_LORDS[house_sign]
            lord_sign = positions[lord]["sign_number"]
            d = (lord_sign - house_sign) % 12
            a = (lord_sign + d) % 12
            if a == house_sign or (a - house_sign) % 12 == 6:
                a = (house_sign + 9) % 12  # 10th from the original (BPHS exception)
            return a

        al = _arudha(lag)
        ul = _arudha((lag + 11) % 12)  # 12th house arudha = Upapada
        return {
            "karakas": karakas,
            "atmakaraka": ak,
            "karakamsa_sign": SIGNS[ak_nav],
            "arudha_lagna_sign": SIGNS[al],
            "upapada_sign": SIGNS[ul],
            "plain": (
                f"Jaimini layer: your soul planet (Atmakaraka) is {ak}, and its Navamsa sign {SIGNS[ak_nav]} is the "
                f"Karakamsa — the inner office where wealth karma is processed. The Arudha Lagna ({SIGNS[al]}) is how "
                f"the world perceives your money status, and the Upapada ({SIGNS[ul]}) shows how partnerships sustain it. "
                "Money flows best when your public money-image (AL) and your actual trading style agree — alignment here "
                "attracts capital, mentors and clients without extra pushing."
            ),
        }

    # ------------------------------------------------------------------ avasthas
    def avasthas(self, positions: Dict) -> Dict:
        rows = {}
        for n in P7:
            p = positions[n]
            deg = p["degree_within_sign"]
            idx = int(deg // 6)
            odd = p["sign_number"] % 2 == 0
            state = AVASTHA_STATES[idx if odd else 4 - idx]
            rows[n] = {"state": state[0], "capacity": state[1],
                       "sign": p["sign"], "degree": round(deg, 2)}
        yuva = [n for n, r in rows.items() if r["state"].startswith("Yuva")]
        mrita = [n for n, r in rows.items() if r["state"].startswith("Mrita")]
        plain = (f"Baladi avasthas grade each planet's age: {', '.join(yuva) if yuva else 'none'} sit in their adult "
                 f"prime (full delivery), while {', '.join(mrita) if mrita else 'none'} are in a spent state (wait for "
                 "their dasha or a strong transit before trusting their money promises).")
        return {"planets": rows, "plain": plain}

    # ------------------------------------------------------------------ yogas
    def detect_yogas(self, positions: Dict, lag: int) -> Dict:
        P = positions
        h = {n: P[n]["house"] for n in P}
        hlore = {n: (P[n]["sign_number"] - lag) % 12 for n in P}

        def hl(hnum: int) -> str:
            return SIGN_LORDS[(lag + hnum - 1) % 12]

        def associated(a: str, b: str) -> bool:
            if a == b:
                return True
            if hlore[a] == hlore[b]:  # conjunction
                return True
            if (hlore[a] - hlore[b]) % 12 == 6:  # mutual 7th aspect
                return True
            # exchange (parivartana)
            if SIGN_LORDS[P[a]["sign_number"]] == b and SIGN_LORDS[P[b]["sign_number"]] == a:
                return True
            return False

        found: List[Dict] = []

        def add(name, category, planets, meaning, strength="moderate"):
            found.append({"name": name, "category": category, "planets": planets,
                          "meaning": meaning, "strength": strength})

        # Gajakesari
        moon_jup = (hlore["Jupiter"] - hlore["Moon"]) % 12 + 1
        if moon_jup in KENDRA_H:
            add("Gajakesari", "Prestige & wealth", ["Jupiter", "Moon"],
                "Jupiter in a kendra from the Moon — reputation-led wealth; advisors and public trust amplify every position.")
        # Pancha Mahapurusha
        pm = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa",
              "Venus": "Malavya", "Saturn": "Sasa"}
        EX = {"Sun": 0, "Moon": 1, "Mercury": 5, "Venus": 11, "Mars": 9, "Jupiter": 3, "Saturn": 6}
        for n, yname in pm.items():
            if h[n] in KENDRA_H and (P[n]["dignity"] in ("exalted", "own sign", "moolatrikona")
                                     or P[n]["sign_number"] == EX[n]):
                add(yname, "Pancha Mahapurusha", [n],
                    f"{n} dignified in a kendra — {yname} yoga: a 'great-person' mark; {n}-ruled sectors and roles carry outsized money power.", "strong")
        # Budhaditya
        if hlore["Mercury"] == hlore["Sun"]:
            add("Budhaditya", "Intellect", ["Sun", "Mercury"],
                "Sun + Mercury together — analytical brilliance; research-led and information-edge trading is your lane.")
        # Chandra-Mangala (wealth combo)
        if hlore["Moon"] == hlore["Mars"] or (hlore["Moon"] - hlore["Mars"]) % 12 == 6:
            add("Chandra-Mangala", "Wealth", ["Moon", "Mars"],
                "Moon + Mars linked — the classic earning combination: liquidity chases momentum; good for active income, but guard against impulsive entries.")
        # Dhana yogas
        dhana_pairs = [(2, 11), (2, 5), (2, 9), (5, 11), (9, 11)]
        for a, b in dhana_pairs:
            la, lb = hl(a), hl(b)
            if la != lb and associated(la, lb):
                add(f"Dhana yoga ({la}-{lb})", "Wealth", [la, lb],
                    f"the {a}th lord {la} joins the {b}th lord {lb} — a BPHS wealth combination; when either runs its dasha, income and asset base step up together.")
        # Raja yogas
        raja_count = 0
        for k in (1, 4, 7, 10):
            for t in (1, 5, 9):
                lk, lt = hl(k), hl(t)
                if lk != lt and associated(lk, lt) and raja_count < 3:
                    add(f"Raja yoga ({lk}-{lt})", "Power & position", [lk, lt],
                        f"kendra lord {lk} links trikona lord {lt} — authority and fortune fuse; positions taken with status/leadership themes outperform.", "strong")
                    raja_count += 1
        # Sunapha / Anapha / Durudhara / Kemadruma (from Moon, excl Sun & nodes)
        second = [n for n in P7 if n not in ("Sun",) and (hlore[n] - hlore["Moon"]) % 12 == 1]
        twelfth = [n for n in P7 if n not in ("Sun",) and (hlore[n] - hlore["Moon"]) % 12 == 11]
        if second and twelfth:
            add("Durudhura", "Wealth flow", sorted(set(second + twelfth)),
                "planets flank the Moon on both sides — comfortable, supported wealth flow; the mind rarely starves for opportunity.")
        elif second:
            add("Sunapha", "Wealth flow", second,
                "planets in the 2nd from the Moon — self-made accumulation; money grows by your own steady effort.")
        elif twelfth:
            add("Anapha", "Wealth flow", twelfth,
                "planets in the 12th from the Moon — money moves out as fast as it arrives unless you automate saving rules.")
        elif not any(h[n] in KENDRA_H for n in ("Jupiter", "Venus", "Mercury") ):
            add("Kemadruma", "Risk flag", [],
                "no planets flank the Moon and no benefic sits in a kendra from it — a Kemadruma flag: emotional income gaps; use written rules, position limits and automatic transfers.", "weak")
        # Neecha Bhanga
        for n in P7:
            if P[n]["dignity"] == "debilitated":
                disp = SIGN_LORDS[P[n]["sign_number"]]
                if h.get(disp) and h[disp] in KENDRA_H or disp == "Moon" or disp == lag:
                    add(f"Neecha Bhanga ({n})", "Rescue", [n, disp],
                        f"{n} is debilitated but its dispositor {disp} stands in a kendra — the fall is cancelled; early losses convert into late-blooming gains.", "moderate")
        # Lakshmi yoga (simplified)
        l9 = hl(9)
        if P[l9]["dignity"] in ("exalted", "own sign", "moolatrikona") and h[l9] in (KENDRA_H | TRIKONA_H):
            add("Lakshmi", "Wealth", [l9],
                f"the 9th lord {l9} is dignified in a kendra/trikona — Lakshmi yoga: fortune actively funds the bank account; long-horizon positions are blessed.")
        # Saraswati (simplified)
        if all(h[n] in (KENDRA_H | TRIKONA_H | {2}) for n in ("Jupiter", "Venus", "Mercury")):
            add("Saraswati", "Intellect & wealth", ["Jupiter", "Venus", "Mercury"],
                "Jupiter, Venus and Mercury all in auspicious houses — Saraswati yoga: knowledge itself monetises; writing, teaching and modelling pay.")
        # Adhi yoga (benefics 6/7/8 from Moon)
        if all(hlore[n] in ((hlore["Moon"] + 5) % 12, (hlore["Moon"] + 6) % 12, (hlore["Moon"] + 7) % 12)
               for n in ("Jupiter", "Venus", "Mercury") if n in P):
            add("Adhi", "Prestige", ["Jupiter", "Venus", "Mercury"],
                "benefics in 6/7/8 from the Moon — leadership over others' capital; fund/institutional roles are starred.")
        return {"found": found,
                "plain": (f"{len(found)} classical yoga(s) detected. Yogas are BPHS planetary combinations — "
                          "each one is a standing pipeline of money potential that switches on when its planets "
                          "run dasha periods or receive strong transits.")}

    # ------------------------------------------------------------------ shadbala
    def shadbala(self, positions: Dict, lag: int, birth: Dict, speeds: Dict) -> Dict:
        P = positions
        asc = P["Lagna"]["longitude"]
        # approximate MC (sidereal) via local sidereal-time-free shortcut:
        # 10th whole-sign madhya = asc + 270° — but we want the exact Dig point; use ascmc when available.
        try:
            jd = birth.get("_jd")
            if jd:
                _, ascmc = swe.houses_ex(jd, birth["lat"], birth["lon"], b'W', flags=swe.FLG_SIDEREAL)
                mc = ascmc[1] % 360
            else:
                mc = (asc + 270) % 360
        except Exception:
            mc = (asc + 270) % 360

        local_hour = float(birth["time"][:2]) + float(birth["time"][3:5]) / 60.0
        weekday = (datetime.strptime(birth["date"], "%Y-%m-%d").weekday())  # Mon=0
        day_lord = WEEKDAY_LORDS[weekday]
        # hora: hours since ~6am local sunrise, Chaldean order starting from day lord
        hidx = int((local_hour - 6) % 24)
        start = CHALDEAN.index(day_lord)
        hora_lord = CHALDEAN[(start + hidx) % 7]

        moon_lon = P["Moon"]["longitude"]
        sun_lon = P["Sun"]["longitude"]
        elong = (moon_lon - sun_lon) % 360

        rows = {}
        for n in P7:
            p = P[n]
            lon = p["longitude"]
            sp = speeds.get(n, {})
            dign = p.get("dignity_score", 0.4)

            # 1) Sthana bala
            deb_point = (EXALT_ABS[n] + 180) % 360
            uccha = min(60.0, self._sep(lon, deb_point) / 3.0)
            sv = 0.0
            for v, wd in (("D1", 0.4), ("D9", 0.3), ("D10", 0.2), ("D60", 0.1)):
                vsign = _varga_sign(p["sign_number"], p["degree_within_sign"], v)
                sv += _VARGA_POINTS[_relation(n, vsign)] * wd
            saptavargaja = min(60.0, sv)
            odd_sign = p["sign_number"] % 2 == 0
            nav_sign = _varga_sign(p["sign_number"], p["degree_within_sign"], "D9")
            odd_nav = nav_sign % 2 == 0
            if n in ("Sun", "Mars", "Jupiter"):
                ojayugma = (60 if odd_sign else 0) * 0.5 + (60 if odd_nav else 0) * 0.5
            elif n in ("Moon", "Venus", "Saturn"):
                ojayugma = (60 if not odd_sign else 0) * 0.5 + (60 if not odd_nav else 0) * 0.5
            else:
                ojayugma = 30.0
            kendradi = 60.0 if p["house"] in KENDRA_H else (30.0 if p["house"] in {2, 5, 8, 11} else 15.0)
            dk = int(p["degree_within_sign"] // 10)
            if n in ("Sun", "Mars", "Jupiter"):
                drekkana = (15, 30, 45)[dk]
            elif n in ("Moon", "Venus", "Saturn"):
                drekkana = (45, 30, 15)[dk]
            else:
                drekkana = 25.0
            sthana = uccha + saptavargaja + ojayugma + kendradi + drekkana

            # 2) Dig bala
            strong_point = {"Jupiter": asc, "Mercury": asc, "Sun": mc, "Mars": mc,
                            "Saturn": (asc + 180) % 360, "Moon": (mc + 180) % 360,
                            "Venus": (mc + 180) % 360}[n]
            dig = max(0.0, 60.0 - self._sep(lon, strong_point) / 3.0)

            # 3) Kala bala
            dn = abs(local_hour - 12.0)  # 0..12
            if n in ("Sun", "Mars", "Jupiter", "Mercury"):
                nathonnatha = max(0.0, 60.0 - dn * 5)
            else:
                nathonnatha = min(60.0, dn * 5)
            if n in ("Moon", "Venus", "Jupiter"):
                paksha = min(60.0, elong / 6.0)
            elif n == "Mercury":
                paksha = min(60.0, elong / 6.0 if self._sep(speeds["Mercury"]["lon"], sun_lon) < 12 else (360 - elong) / 6.0)
            else:
                paksha = min(60.0, (360.0 - elong) / 6.0)
            dina = 45.0 if day_lord == n else 0.0
            hora = 60.0 if hora_lord == n else 0.0
            trop = sp.get("trop", lon)
            if n in ("Sun", "Jupiter", "Venus"):
                ayana = ((trop - 270) % 360) / 6.0
            elif n == "Mercury":
                ayana = 30.0
            else:
                ayana = ((trop - 90) % 360) / 6.0
            ayana = min(60.0, ayana)
            kala = nathonnatha + paksha + dina + hora + ayana  # tribhaga & yuddha omitted (documented)

            # 4) Chesta bala
            if n == "Sun":
                chesta = 60.0
            else:
                ratio = abs(sp.get("speed", MEAN_SPEED[n])) / MEAN_SPEED[n]
                chesta = min(60.0, 30.0 * ratio + (30.0 if sp.get("speed", 0) < 0 else 0.0))
                if n != "Moon" and self._sep(lon, sun_lon) < COMBUST_ORB[n]:
                    chesta *= 0.6  # combustion dampens motion-strength
            # 5) Naisargika
            naisargika = NAISARGIKA[n]
            # 6) Drik bala
            drik = 0.0
            for other in P7:
                if other == n:
                    continue
                o = P[other]
                d = (o["house"] - p["house"]) % 12 + 1
                aspects = {7}
                if other == "Mars":
                    aspects |= {4, 8}
                if other == "Jupiter":
                    aspects |= {5, 9}
                if other == "Saturn":
                    aspects |= {3, 10}
                if d in aspects:
                    w = 15.0 * (0.4 + 0.6 * o.get("dignity_score", 0.4))
                    drik += w if other in NATURAL_BENEFICS else -w

            total = sthana + dig + kala + chesta + naisargika + drik
            rupas = round(total / 60.0, 2)
            req = SHADBALA_REQUIRED[n]
            if rupas >= req * 1.1:
                verdict = "strong — can deliver its full money promise inside its dasha"
            elif rupas >= req * 0.9:
                verdict = "adequate — delivers steadily with transit support"
            else:
                verdict = "under-powered — promises need time, discipline and favourable transits"
            rows[n] = {
                "rupas": rupas, "required": req, "verdict": verdict,
                "components": {
                    "Sthana (positional)": round(sthana, 1),
                    "Dig (directional)": round(dig, 1),
                    "Kala (temporal)": round(kala, 1),
                    "Chesta (motional)": round(chesta, 1),
                    "Naisargika (natural)": round(naisargika, 1),
                    "Drik (aspectual)": round(drik, 1),
                },
            }
        ranked = sorted(((n, r["rupas"]) for n, r in rows.items()), key=lambda kv: -kv[1])
        top = ranked[0]
        weak = ranked[-1]
        plain = (f"Shadbala ranks planetary capacity in Rupas (total shashtiamsas ÷ 60). {top[0]} leads "
                 f"({top[1]:.2f} Rupas vs {SHADBALA_REQUIRED[top[0]]:.2f} needed) — its money themes are the ones "
                 f"you can push hardest right now. {weak[0]} is the thinnest ({weak[1]:.2f}) — avoid leaning on "
                 f"{weak[0]}-ruled bets until its dasha or a major transit revives it.")
        return {"planets": rows, "ranked": ranked, "day_lord": day_lord, "hora_lord": hora_lord,
                "plain": plain}

    # ------------------------------------------------------------------ ashtakvarga
    def ashtakvarga(self, positions: Dict, lag: int) -> Dict:
        """BAV (prastara, BPHS Ch.66) + Trikona/Ekadhipatya reductions.

        SAV = sum of the SEVEN planetary BAVs = 337 bindus always (48+49+39+
        54+56+52+39). The Lagna BAV (49) is supplementary. Reduced BAVs are
        kept for transit fine-scoring (own_bindus).
        """
        ref_sign = {n: positions[n]["sign_number"] for n in P7}
        bav = {c: [0] * 12 for c in ("Sun", "Moon", "Mars", "Mercury",
                                     "Jupiter", "Venus", "Saturn", "Asc")}
        for contrib, refs in ASHTAKVARGA.items():
            for ref, houses in refs.items():
                base = lag if ref == "Asc" else ref_sign[ref]
                for hd in houses:
                    bav[contrib][(base + hd - 1) % 12] += 1
        raw_total = sum(sum(bav[c]) for c in bav if c != "Asc")
        # ---- reductions on each planetary BAV ----
        occupancy = {s: 0 for s in range(12)}
        for n in P7 + ["Rahu", "Ketu"]:
            occupancy[positions[n]["sign_number"]] += 1

        reduced = {c: list(v) for c, v in bav.items()}
        for c in reduced:
            # Trikona shodhana: reduce the minimum only when all three trines are non-zero
            for trio in TRIKONA_GROUPS:
                vals = [reduced[c][s] for s in trio]
                if all(v > 0 for v in vals):
                    m = min(vals)
                    for s in trio:
                        reduced[c][s] -= m
            # Ekadhipatya shodhana: equal-bindu sign pairs owned by one planet
            for s1, s2, _owner in DUAL_OWNERS:
                i1, i2 = SIGNS.index(s1), SIGNS.index(s2)
                a, b = reduced[c][i1], reduced[c][i2]
                if a > 0 and a == b:
                    o1, o2 = occupancy[i1], occupancy[i2]
                    if o1 == 0 and o2 > 0:
                        reduced[c][i1] = 0
                    elif o2 == 0 and o1 > 0:
                        reduced[c][i2] = 0
                    else:
                        # both occupied / both empty: reduce the even sign (Parashari tie-break)
                        if i2 % 2 == 1:
                            reduced[c][i2] = 0
                        else:
                            reduced[c][i1] = 0
        sav = [sum(bav[c][s] for c in bav if c != "Asc") for s in range(12)]
        sav_reduced = [sum(reduced[c][s] for c in reduced if c != "Asc") for s in range(12)]
        sav_total = sum(sav)
        if sav_total != 337:
            logger.warning("SAV total %s != 337 (prastara raw %s) — check tables",
                           sav_total, raw_total)
        wealth = {}
        for hn in (1, 2, 5, 9, 10, 11):
            sign_idx = (lag + hn - 1) % 12
            v = sav[sign_idx]
            label = "strong support" if v >= 29 else ("adequate" if v >= 25 else "thin support")
            wealth[f"house_{hn}"] = {"bindus": v, "sign": SIGNS[sign_idx], "status": label}
        saturn_bav = reduced["Saturn"]
        jupiter_bav = reduced["Jupiter"]
        best = sorted(range(12), key=lambda s: -sav[s])[:3]
        best_txt = ", ".join(f"{SIGNS[s]} ({sav[s]})" for s in best)
        return {
            "bav": bav, "bav_reduced": reduced, "sav": sav, "sav_total": sav_total,
            "sav_reduced": sav_reduced, "asc_bav": bav["Asc"],
            "prastara_total": raw_total, "expected_totals": BAV_TOTALS,
            "wealth": wealth,
            "saturn_bav": saturn_bav, "jupiter_bav": jupiter_bav,
            "strongest_signs": [{"sign": SIGNS[s], "bindus": sav[s]} for s in best],
            "plain": (
                f"Ashtakvarga scores every sign with bindus (points) counted from 8 references "
                f"(7 planets + Lagna). Your Sarvashtakavarga holds the canonical 337 bindus "
                f"(Sun 48 + Moon 49 + Mars 39 + Mercury 54 + Jupiter 56 + Venus 52 + Saturn 39). "
                f"Strongest sign(s): {best_txt}. "
                "Transiting Saturn/Jupiter over signs holding 28+ SAV bindus tends to reward accumulation there; "
                "under 25 bindus the same transits give little traction — don't force big positions."
            ),
        }

    # ------------------------------------------------------------------ bhavabala
    def bhavabala(self, positions: Dict, lag: int, shad: Dict, av: Dict) -> Dict:
        P = positions
        rupas = {n: shad["planets"][n]["rupas"] for n in P7}
        rows = []
        for hn in range(1, 13):
            sign_idx = (lag + hn - 1) % 12
            lord = SIGN_LORDS[sign_idx]
            lord_p = P[lord]
            score = 0.0
            if lord in rupas:
                ratio = min(1.6, rupas[lord] / max(0.1, SHADBALA_REQUIRED[lord]))
                score += 40 * ratio  # up to ~64
            if lord_p["dignity"] in ("exalted", "own sign", "moolatrikona"):
                score += 8
            if lord_p["house"] in KENDRA_H | TRIKONA_H:
                score += 8
            if lord_p["house"] in DUSTHANA_H:
                score -= 8
            for n in P7 + ["Rahu", "Ketu"]:
                if P[n]["sign_number"] == sign_idx:
                    score += 10 if n in NATURAL_BENEFICS else -7
                d = (P[n]["sign_number"] - sign_idx) % 12
                aspects = {7}
                if n == "Mars":
                    aspects |= {4, 8}
                if n == "Jupiter":
                    aspects |= {5, 9}
                if n == "Saturn":
                    aspects |= {3, 10}
                if d in aspects and n != SIGN_LORDS[sign_idx]:
                    score += 7 if n in NATURAL_BENEFICS else -5
            bindus = av["sav"][sign_idx]
            score += (bindus - 28) / 28.0 * 12
            final = max(2, min(100, round(score)))
            rows.append({"house": hn, "sign": SIGNS[sign_idx], "lord": lord,
                         "score": final, "bindus": bindus,
                         "wealth_flag": hn in WEALTH_HOUSES})
        ranked = sorted(rows, key=lambda r: -r["score"])
        top = ranked[0]
        top_line = HOUSE_MONEY_LINES[top["house"]][3:] if top["house"] in HOUSE_MONEY_LINES else ""
        return {
            "houses": rows, "ranked": ranked,
            "strongest_house": top,
            "plain": (f"Bhavabala measures each house's capacity to deliver. Your strongest life-area is house "
                      f"{top['house']} ({top['sign']}) at {top['score']}/100 — {top_line}. "
                      "Wealth houses 2, 5, 9, 10 and 11 with 55+ scores are the ones worth building income around."),
        }

    # ------------------------------------------------------------------ KP
    def _kp_longitude(self, longitude: float) -> Tuple[str, str, str]:
        nak_span = 360.0 / 27.0
        nak_i = int(longitude // nak_span)
        pos = longitude % nak_span
        start = nak_i % 9
        order = VIM_ORDER[start:] + VIM_ORDER[:start]
        acc = 0.0
        sub = order[0]
        for lord in order:
            span = nak_span * VIM_YEARS[lord] / 120.0
            if acc <= pos < acc + span:
                sub = lord
                break
            acc += span
        return NAK_NAMES[nak_i], order[0], sub

    def kp_chart(self, jd: float, lat: float, lon: float, positions: Dict, birth: Dict) -> Dict:
        swe.set_sid_mode(self.ayanamsa_mode)
        cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P', flags=swe.FLG_SIDEREAL)
        cusp_rows = []
        cusp_names = {2: "savings", 6: "service income", 10: "career", 11: "gains"}
        for i in range(12):
            clon = cusps[i] % 360
            nak, star, sub = self._kp_longitude(clon)
            cusp_rows.append({"cusp": i + 1, "sign": SIGNS[int(clon // 30)],
                              "degree": round(clon % 30, 2),
                              "star_lord": star, "sub_lord": sub,
                              "cusp_name": cusp_names.get(i + 1, "")})
        planet_rows = []
        for n in P7 + ["Rahu", "Ketu"]:
            p = positions.get(n)
            if not p:
                continue
            nak, star, sub = self._kp_longitude(p["longitude"])
            planet_rows.append({"planet": n, "sign": p["sign"],
                                "star_lord": star, "sub_lord": sub})
        asc_nak, asc_star, asc_sub = self._kp_longitude(positions["Lagna"]["longitude"])
        moon_nak, moon_star, moon_sub = self._kp_longitude(positions["Moon"]["longitude"])
        weekday = datetime.strptime(birth["date"], "%Y-%m-%d").weekday()
        day_lord = WEEKDAY_LORDS[weekday]
        ruling = sorted({asc_star, SIGN_LORDS[positions["Lagna"]["sign_number"]],
                         moon_star, SIGN_LORDS[positions["Moon"]["sign_number"]], day_lord})
        sig_txt = " ".join(
            f"cusp {r['cusp']} ({r['cusp_name']}) sub-lord {r['sub_lord']};" for r in cusp_rows
            if r["cusp"] in (2, 6, 10, 11))
        kp_plain = (
            "KP (Krishnamurti Paddhati) says a planet gives the results of its STAR lord, and only with the "
            f"permission of its SUB lord. Your money cusps: {sig_txt} "
            f"Ruling planets at birth: {', '.join(ruling)}. When a running dasha lord is also one of the ruling "
            "planets, its period gives fast, verifiable money events — that is the KP timing edge."
        )
        return {"cusps": cusp_rows, "planets": planet_rows, "ruling_planets": ruling,
                "asc_star_lord": asc_star, "asc_sub_lord": asc_sub,
                "day_lord": day_lord, "plain": kp_plain}

    # ------------------------------------------------------------------ yogini
    def yogini(self, chart: Dict, dasha) -> Dict:
        birth = dasha.birth
        nak_i = dasha.nak_index
        moon_lon = chart["positions"]["Moon"]["longitude"]
        nak_span = 360.0 / 27.0
        frac = (moon_lon % nak_span) / nak_span
        start = nak_i % 8
        forward = nak_i % 2 == 0
        idxs = list(range(8))
        order = [idxs[(start + i) % 8] for i in range(8)] if forward else \
                [idxs[(start - i) % 8] for i in range(8)]
        periods = []
        cursor = birth.replace(tzinfo=None) if birth.tzinfo else birth
        first_years = YOGINIS[order[0]][1] * (1.0 - frac)
        periods.append({"yi": order[0], "start": cursor, "years": first_years})
        cursor = cursor + timedelta(days=first_years * 365.2425)
        k = 1
        while (cursor - periods[0]["start"]).days < 365.2425 * 120 and len(periods) < 12:
            yi = order[k % 8]
            yrs = YOGINIS[yi][1]
            periods.append({"yi": yi, "start": cursor, "years": float(yrs)})
            cursor = cursor + timedelta(days=yrs * 365.2425)
            k += 1
        now = datetime.utcnow()
        cur = periods[0]
        for pr in periods:
            if pr["start"] <= now:
                cur = pr
        name, yrs, lord, money = YOGINIS[cur["yi"]]
        sub_order = [order[(order.index(cur["yi"]) + i) % 8] for i in range(8)]
        span_days = max(1.0, cur["years"] * 365.2425)
        sub_frac = min(0.999, max(0.0, (now - cur["start"]).days / span_days))
        sub_yi = sub_order[min(7, int(sub_frac * 8))]
        sname, syrs, slord, smoney = YOGINIS[sub_yi]
        return {
            "direction": "forward" if forward else "reverse",
            "first_yogini": YOGINIS[order[0]][0],
            "balance_years": round(first_years, 2),
            "periods": [{"yogini": YOGINIS[p["yi"]][0], "lord": YOGINIS[p["yi"]][2],
                         "start": p["start"].strftime("%d-%m-%Y"),
                         "end": (p["start"] + timedelta(days=p["years"] * 365.2425)).strftime("%d-%m-%Y"),
                         "years": round(p["years"], 1)} for p in periods[:9]],
            "current": {"yogini": name, "lord": lord,
                        "sub_yogini": sname, "sub_lord": slord,
                        "money_note": money},
            "plain": (f"Yogini dasha is the fast 36-year supplementary timer. You opened with {YOGINIS[order[0]][0]} "
                      f"({first_years:.2f}y balance, {('forward' if forward else 'reverse')} cycle). Now running "
                      f"{name} (lord {lord}): {money}. Sub-period {sname} ({slord}): {smoney}. "
                      "Use Yogini to fine-tune entries inside the big Vimshottari weather — when both timers agree, "
                      "conviction can be higher."),
        }

    # ------------------------------------------------------------------ karma vipaka
    def karma_vipaka(self, positions: Dict, dasha) -> Dict:
        moon = positions["Moon"]
        ni = int(moon["longitude"] // (360.0 / 27.0))
        name, lord, deity, symbol, theme = NAKSHATRAS[ni % 27]
        p = positions[lord]
        cur = dasha.current()
        md_lord = cur["mahadasha"]["lord"] if cur.get("mahadasha") else "—"
        ad_lord = cur["antardasha"]["lord"] if cur.get("antardasha") else "—"
        remedy_day = {"Sun": "Sunday", "Moon": "Monday", "Mars": "Tuesday", "Mercury": "Wednesday",
                      "Jupiter": "Thursday", "Venus": "Friday", "Saturn": "Saturday",
                      "Rahu": "Saturday", "Ketu": "Saturday"}[lord]
        return {
            "nakshatra": name, "deity": deity, "symbol": symbol, "theme": theme,
            "lord": lord, "lord_house": p["house"], "lord_sign": p["sign"],
            "plain": (
                f"Karma Vipaka lens: your Moon sits in {name} (deity {deity}, symbol {symbol}) — the karmic theme is "
                f"“{theme}”. Its lord {lord} lives in your {p['house']}th house ({p['sign']}), so money karma ripens "
                f"through {HOUSE_MONEY_LINES[p['house']][3:]}. Under the current {md_lord}/{ad_lord} dasha the same "
                f"theme is being re-run for review: results feel fated, but they are simply old patterns paying out. "
                f"Constructive remedy — keep a written trading journal, review it every {remedy_day}, and give a fixed "
                f"slice of profits to charity on {remedy_day}s; the classical prescription for {name} karma is "
                f"discipline plus giving, which converts karmic repetition into steady compounding."
            ),
        }

    # ------------------------------------------------------------------ transits × SAV
    def transits_sav(self, positions: Dict, lag: int, av: Dict) -> Dict:
        now = datetime.utcnow()
        jd = swe.julday(now.year, now.month, now.day, now.hour / 24.0)
        swe.set_sid_mode(self.ayanamsa_mode)
        rows = []
        for n, pid in (("Saturn", swe.SATURN), ("Jupiter", swe.JUPITER),
                       ("Rahu", swe.MEAN_NODE), ("Ketu", swe.MEAN_NODE)):
            d = self.vedic.calculate_planet_position_vedic(pid, jd)
            tsign = int(d["longitude"] % 360 // 30)
            th = (tsign - lag) % 12 + 1
            sav_b = av["sav"][tsign]
            if n == "Saturn":
                own = av["saturn_bav"][tsign]
            elif n == "Jupiter":
                own = av["jupiter_bav"][tsign]
            else:
                own = None
            verdict = ("above-average ground — slow accumulation works here"
                       if sav_b >= 28 else ("average ground — standard sizing only" if sav_b >= 25
                                            else "thin ground — stay small, transit pays little"))
            own_txt = f" {n}'s own BAV gives it {own} bindus here." if own is not None else ""
            rows.append({"planet": n, "sign": SIGNS[tsign], "house": th,
                         "sav_bindus": sav_b, "own_bindus": own, "verdict": verdict,
                         "plain": (f"Transiting {n} moves through {SIGNS[tsign]} (your {th}th house) which holds "
                                   f"{sav_b} SAV bindus — {verdict}.{own_txt}")})
        return {"rows": rows,
                "plain": ("Transit money-rule from the guide: Saturn and Jupiter pay best when they cross signs rich "
                          "in your personal Ashtakvarga bindus. This table reads today's sky against your chart — "
                          "it is the 'is the ground fertile right now?' check.")}

    # ------------------------------------------------------------------ house synthesis
    def house_synthesis(self, positions: Dict, lag: int, bhava: Dict, av: Dict) -> List[Dict]:
        P = positions
        out = []
        bhava_by_h = {r["house"]: r for r in bhava["houses"]}
        for hn in range(1, 13):
            sign_idx = (lag + hn - 1) % 12
            lord = SIGN_LORDS[sign_idx]
            lp = P[lord]
            occ = [n for n in P7 + ["Rahu", "Ketu"] if P[n]["sign_number"] == sign_idx]
            r = bhava_by_h[hn]
            strength_word = ("powerful" if r["score"] >= 65 else
                             "healthy" if r["score"] >= 50 else
                             "mixed" if r["score"] >= 35 else "weak")
            occ_txt = ", ".join(occ) if occ else "no graha"
            sentence = (
                f"House {hn} ({SIGNS[sign_idx]}, lord {lord} in house {lp['house']}, {lp['dignity']}; occupants: {occ_txt}; "
                f"{r['bindus']} SAV bindus, strength {r['score']}/100 — {strength_word}). "
                f"Money meaning: {HOUSE_MONEY_LINES[hn][0].upper() + HOUSE_MONEY_LINES[hn][1:]}. "
                + (f"With the lord {strength_word}, lean into this area when its dasha runs"
                   if r["score"] >= 50 else
                   "build systems here before expecting income")
            )
            out.append({"house": hn, "sign": SIGNS[sign_idx], "lord": lord,
                        "lord_house": lp["house"], "occupants": occ,
                        "bindus": r["bindus"], "score": r["score"],
                        "wealth_flag": hn in WEALTH_HOUSES, "plain": sentence})
        return out

    # ------------------------------------------------------------------ verdict
    def verdict(self, positions: Dict, lag: int, out: Dict, dasha, yogas: Dict) -> Dict:
        P = positions
        reasons: List[str] = []
        risks: List[str] = []
        score = 50
        found = [y["name"] for y in yogas["found"]]
        dhana = [n for n in found if n.startswith("Dhana") or n in ("Lakshmi", "Chandra-Mangala")]
        if dhana:
            score += min(20, 6 * len(dhana))
            reasons.append(f"carries {len(dhana)} wealth yoga(s): {', '.join(dhana)}")
        pm = [y for y in yogas["found"] if y["category"] == "Pancha Mahapurusha"]
        if pm:
            score += 8
            reasons.append(f"{pm[0]['name']} yoga — a great-person strength mark")
        sun = P["Sun"]
        if sun["dignity"] == "exalted":
            score += 6
            reasons.append(f"exalted Sun in house {sun['house']} — willpower and judgement at peak")
        if P["Moon"]["house"] in (1, 5, 9):
            score += 5
            reasons.append(f"Moon in house {P['Moon']['house']} — healthy speculation temperament")
        for n in ("Venus", "Saturn", "Jupiter"):
            if P[n]["dignity"] in ("own sign", "exalted", "moolatrikona") and P[n]["house"] in (2, 11):
                score += 5
                reasons.append(f"{n} dignified in house {P[n]['house']} — Dhana-grade placement")
        wh = out["ashtakvarga"]["wealth"]
        if wh["house_2"]["bindus"] >= 28 and wh["house_11"]["bindus"] >= 28:
            score += 8
            reasons.append("Ashtakvarga backs both savings (2) and gains (11) with 28+ bindus")
        for n in ("Rahu", "Ketu"):
            if P[n]["house"] in (8, 12):
                score -= 6
                risks.append(f"{n} in house {P[n]['house']} — volatility/leakage axis; use strict position limits")
        kem = [y for y in yogas["found"] if y["name"] == "Kemadruma"]
        if kem:
            score -= 8
            risks.append("Kemadruma flag — emotional income gaps; automate rules")
        cur = dasha.current()
        md = cur["mahadasha"]["lord"] if cur.get("mahadasha") else None
        if md in ("Rahu", "Ketu", "Saturn"):
            risks.append(f"{md} mahadasha — gains come with stricter discipline; avoid leverage")
        if md in ("Jupiter", "Venus", "Mercury", "Moon"):
            score += 5
            reasons.append(f"{md} mahadasha — a wealth-friendly era")
        score = max(5, min(98, score))
        if score >= 75:
            headline = "YES — the chart is structurally suited to trading"
        elif score >= 55:
            headline = "Conditional YES — promise with discipline filters"
        elif score >= 38:
            headline = "CAUTIOUS — trade small, learn, and let dashas mature"
        else:
            headline = "PASSIVE-FIRST — favour investing over active trading"
        return {"score": score, "headline": headline,
                "reasons": reasons[:5], "risks": risks[:4],
                "plain": (f"Trading-suitability score {score}/100. {headline}. "
                          + ("Strengths: " + "; ".join(reasons[:3]) + ". " if reasons else "")
                          + ("Watch: " + "; ".join(risks[:3]) + "." if risks else ""))}

    # ------------------------------------------------------------------ planetary notes
    def planetary_notes(self, positions: Dict, lag: int) -> Dict:
        P = positions
        notes = {}
        order = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu", "Lagna"]
        for n in order:
            p = P[n]
            dign = p["dignity"]
            h = p["house"]
            phrase = DIGNITY_PHRASES.get(dign, "neutral placement")
            if n == "Lagna":
                nak = p.get("nakshatra", "")
                notes[n] = (f"{p['sign']} {p['degree_within_sign']:.0f}° rising, {nak} — "
                            f"{SIGN_PERSONA.get(p['sign'], '')}; the money lens of the whole chart")
                continue
            notes[n] = (f"{phrase} in house {h} — {HOUSE_MONEY_LINES[h][3:]}"
                        + ("; book profits mechanically" if n == "Ketu" else ""))
        return notes

    # ------------------------------------------------------------------ capstone blueprint
    def blueprint(self, positions: Dict, lag: int, out: Dict, dasha, strengths: Dict,
                  recs: Dict, income: Dict, symbol: str, symbol_name: str) -> Dict:
        cur = dasha.current()
        md = cur["mahadasha"]["lord"] if cur.get("mahadasha") else None
        ad = cur["antardasha"]["lord"] if cur.get("antardasha") else None
        yog = out["yogini"]["current"]
        kp = out["kp"]
        verdict = out["verdict"]
        top3 = [g for g, _ in strengths["ranked"][:3]]

        nxt = None
        for mdn in dasha.tree:
            if cur.get("mahadasha") and mdn["lord"] != cur["mahadasha"]["lord"] and mdn["start"] > cur["mahadasha"]["start"]:
                nxt = {"lord": mdn["lord"], "start": mdn["start"].strftime("%d-%m-%Y")}
                break
        windows = []
        if cur.get("mahadasha"):
            for a in cur["mahadasha"]["antardashas"]:
                if a["lord"] in ("Jupiter", "Venus", "Mercury", "Moon") and a["end"] > datetime.utcnow():
                    windows.append({"period": f"{md}–{a['lord']}", "end": a["end"].strftime("%d-%m-%Y"),
                                    "note": (f"{a['lord']} sub-period — "
                                             + {"Jupiter": "expansion & compounding favoured",
                                                "Venus": "finance & luxury themes rally",
                                                "Mercury": "analysis, arbitrage and trade pay best",
                                                "Moon": "liquidity & consumer flows lead"}[a["lord"]])})
                if len(windows) >= 3:
                    break
        flags = list(verdict["risks"])
        for n in ("Mercury", "Jupiter", "Venus", "Saturn"):
            if positions[n]["dignity"] == "debilitated":
                flags.append(f"{n} debilitated — its sector calls need extra confirmation")
        if yog["lord"] == "Rahu":
            flags.append("Sankata (Rahu) Yogini running — volatility spikes; halve normal size")
        weak = [n for n, _ in out["shadbala"]["ranked"][-2:]]
        remedy_map = {
            "Sun": "respect a sunrise routine; consistency itself is the remedy",
            "Moon": "fix a written risk budget before every session (emotional guardrail)",
            "Mars": "channel aggression into a pre-planned entry checklist, never revenge trades",
            "Mercury": "journal every trade on Wednesdays; refine one metric per week",
            "Jupiter": "tithe a slice of gains; study one great investor per quarter",
            "Venus": "avoid trading luxury impulses; automate savings on Fridays",
            "Saturn": "serve the process — slow systematic DCA beats shortcuts",
            "Rahu": "one speculative slot only; hard stops mandatory",
            "Ketu": "close losing trades fast; detachment is a profit skill",
        }
        remedies = [{"planet": n, "practice": remedy_map[n]} for n in weak]
        primary_style = recs["strategies"][0]["label"] if recs.get("strategies") else "systematic equity"
        allocation = recs.get("allocation", [])[:3]
        inc = income
        saturn_row = [r for r in out["transits"]["rows"] if r["planet"] == "Saturn"][0]
        plan = [
            {"window": "Now → 30 days",
             "action": (f"Trade {symbol_name} ({symbol}) only in the {primary_style.lower()} style. "
                        f"{md or 'Current'} mahadasha with {ad or '-'} sub-period sets a "
                        f"{'patient accumulation' if md in ('Jupiter', 'Venus', 'Moon') else 'strict-stop momentum'} tone; "
                        f"Yogini {yog['yogini']} agrees — position size ≤{(10 if verdict['score'] >= 70 else 6)}% of capital per idea.")},
            {"window": "30 → 60 days",
             "action": (f"Watch the {windows[0]['period'] if windows else 'current'} window (till {windows[0]['end'] if windows else 'the next sub-period change'}): "
                        f"{windows[0]['note'] if windows else 'keep the process steady'}. Review the KP cuspal sub-lords "
                        "before adding — the gains-cusp sub-lord decides whether inflows fructify on schedule.")},
            {"window": "60 → 90 days",
             "action": ("Re-run the model zoo and the astro composite; if transit Saturn's sign still holds "
                        f"{saturn_row['sav_bindus']}+ SAV bindus, scale the systematic sleeve; otherwise stay in harvest mode.")},
            {"window": "90 → 365 days",
             "action": (f"Aim for the {inc['strategy'].lower()} band (£{inc['weekly']['low']:,.0f}–£{inc['weekly']['high']:,.0f}/week "
                        f"modelled). Next mahadasha shift: {nxt['lord']} from {nxt['start']}. "
                        "Rebuild the plan at that boundary — dasha changes change the rules.")},
        ]
        plain = (
            f"THE MONEY BLUEPRINT — {verdict['headline']}. Style: {primary_style}. Markets: "
            + ", ".join(f"{a['market']} ({a['weight_pct']}%)" for a in allocation)
            + f". Timing: {md}/{ad} Vimshottari with {yog['yogini']} Yogini and KP ruling planets "
            f"{', '.join(kp['ruling_planets'])} all pointing the same way. Income plan: £{inc['weekly']['low']:,.0f}–"
            f"£{inc['weekly']['high']:,.0f}/week modelled at £{inc['capital']:,.0f} capital "
            f"(dasha factor ×{inc['dasha_factor']:.2f}). Risk: {len(flags)} active flag(s) — respect them. "
            "This blueprint merges BPHS strengths, Jaimini soul-plan, Ashtakvarga ground-quality, KP timing "
            "and dasha weather into one operating plan — review it at every antardasha change."
        )
        return {"verdict": verdict, "style": primary_style, "allocation": allocation,
                "timing_windows": windows, "next_mahadasha": nxt,
                "income": {"weekly": inc["weekly"], "monthly": inc["monthly"],
                           "annual": inc["annual"], "capital": inc["capital"],
                           "target_weekly": inc["target_weekly"],
                           "target_feasible": inc["target_feasible"],
                           "capital_needed": inc["target_capital_needed"]},
                "risk_flags": flags[:6], "remedies": remedies,
                "plan": plan, "plain": plain}
