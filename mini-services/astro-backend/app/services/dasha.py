"""
Vimshottari Dasha engine — drikpanchang-standard Mahadasha / Antardasha / Pratyantardasha.

Rectified logic (this is the fix for "Antardasha doesn't seem correct"):
  1. Mahadasha sequence starts from the lord of the Moon's nakshatra at birth,
     and continues in the fixed Vimshottari order.
  2. The FIRST mahadasha runs only for the BALANCE (years * (1 - elapsed_fraction)).
  3. Antardashas (bhuktis) inside a Mahadasha ALWAYS start with the Mahadasha
     lord itself, then proceed in Vimshottari order (MD lord -> next lord -> ...),
     wrapping cyclically through all nine grahas.
  4. Antardasha length = MD_years * (AD_lord_years / 120).  The nine ADs inside
     any MD therefore sum EXACTLY to the MD length.
  5. Pratyantardashas follow the same rule one level deeper inside each AD.
  6. Year length = 365.2425 solar days (drikpanchang convention).
  7. v1.3 fix — the birth mahadasha is NOT compressed into its balance. It is laid
     out at full length from its virtual start (birth - elapsed portion), and every
     antardasha / pratyantardasha that finished before birth is dropped; the one
     running at birth is clipped to start at birth. This is how drikpanchang lists
     the first mahadasha (e.g. a native born late in Sun MD starts mid-way, in a
     later AD such as Rahu or Jupiter, not in Sun/Sun).
"""
import swisseph as swe
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Fixed Vimshottari order, starting from Ketu (Ashwini's lord)
LORD_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
LORD_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}
TOTAL_YEARS = 120.0
YEAR_DAYS = 365.2425

# Nakshatra -> ruling lord (Ashwini=0 ... Revati=26). Order repeats every 9.
NAKSHATRA_LORDS = [LORD_ORDER[i % 9] for i in range(27)]

LORD_GLYPHS = {
    "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me", "Jupiter": "Ju",
    "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke",
}

LORD_THEMES = {
    "Sun": "leadership, government, authority, energy and recognition; bold moves favour you",
    "Moon": "public sentiment, liquidity, consumer demand, FMCG and care-driven themes",
    "Mars": "energy, metals, property, engineering and fast momentum trades; act decisively",
    "Mercury": "analysis, trade, communication, technology and arbitrage; best for careful, calculated bets",
    "Jupiter": "expansion, banking, education, long-term wealth compounding; favour quality and patience",
    "Venus": "luxury, finance, beauty, entertainment and comfort demand; steady accumulation works",
    "Saturn": "discipline, infrastructure, labour-heavy sectors; slow grind, systemise and automate",
    "Rahu": "innovation, speculation, tech manias, unconventional assets; ride trends with strict stops",
    "Ketu": "detachment, research, spiritual/technical niches; close loose ends, avoid over-exposure",
}

DASHA_INTERPRETATIONS = {
    "Sun": "A Sun mahadasha spotlights visibility and leadership. Career and authority matters grow; markets reward courage in large-cap and government-linked names. Watch ego-driven over-risk in June–July seasonal lows.",
    "Moon": "A Moon mahadasha ties your fortune to crowd mood and liquidity. Consumer, FMCG, pharma and public-facing businesses flourish. Emotional trading is the main risk — automate rules.",
    "Mars": "A Mars mahadasha brings drive and competition. Energy, metals, defence and real estate surge; quick swings suit you. Avoid revenge-trading — Mars punishes anger.",
    "Mercury": "A Mercury mahadasha is the analyst's era. Trading, technology, media and logistics prosper. Best period of all for systematic, data-driven strategies — build and refine your models now.",
    "Jupiter": "A Jupiter mahadasha expands wealth steadily. Banking, insurance, education and gold do well. Long-horizon investing and ethical positions compound fastest.",
    "Venus": "A Venus mahadasha blesses comfort and finance. Luxury, autos, beauty, entertainment and financial services rally. Partnerships and joint ventures are favoured.",
    "Saturn": "A Saturn mahadasha tests then rewards discipline. Infrastructure, cement, mining and elderly-care sectors matter. Slow, systematic wealth building — avoid shortcuts and leverage.",
    "Rahu": "A Rahu mahadasha amplifies ambition and speculation. Tech, crypto, foreign and unconventional themes spike. Win big with strict position sizing; bubbles burst inside this dasha.",
    "Ketu": "A Ketu mahadasha dissolves attachments. Research, spirituality, healing and niche technology suit the era. Simplify the portfolio; surrendering a losing trade is a win here.",
}


# One-line "what this period means for trading" per lord, at each dasha level.
TRADING_LINES = {
    "MD": {
        "Sun": "Multi-year backdrop favours large-cap leaders, PSU/energy and gold; build core positions, avoid ego-sized bets.",
        "Moon": "Multi-year backdrop tracks crowd liquidity — consumer/FMCG/pharma lead; automate rules so mood never sizes a trade.",
        "Mars": "Multi-year backdrop rewards momentum in energy, metals, realty, defence; trade breakouts with hard stops.",
        "Mercury": "Multi-year backdrop is ideal for systematic, data-driven trading in IT/telecom/media; build and refine models.",
        "Jupiter": "Multi-year backdrop favours compounding in banks, insurers, quality growth; let winners run, add on dips.",
        "Venus": "Multi-year backdrop favours finance, autos, luxury, consumer brands; steady accumulation beats churn.",
        "Saturn": "Multi-year backdrop is slow and structural — infra, metals, value; DCA, low leverage, long holds.",
        "Rahu": "Multi-year backdrop amplifies tech/foreign/speculative themes; one speculative sleeve, strict position caps.",
        "Ketu": "Multi-year backdrop of detachment — simplify, cut losers fast, favour niche research and pharma.",
    },
    "AD": {
        "Sun": "This sub-period (months–years) favours conviction trades in market leaders; size normally, keep stops honest.",
        "Moon": "This sub-period follows sentiment and liquidity; trade with the crowd, never against a panic.",
        "Mars": "This sub-period brings sharp swings; favour short swing trades, take profits quickly.",
        "Mercury": "This sub-period rewards analysis and shorter-term trading; good time to test and tune strategies.",
        "Jupiter": "This sub-period is expansionary; scale up quality positions gradually, best for investing.",
        "Venus": "This sub-period is comfortable for steady accumulation and income strategies (covered calls, dividends).",
        "Saturn": "This sub-period tests patience; reduce leverage, accumulate slowly, expect delays before payoff.",
        "Rahu": "This sub-period brings sudden spikes; trade smaller, use hard stops, avoid FOMO entries.",
        "Ketu": "This sub-period favours closing loose ends; trim, take profits, avoid opening many new positions.",
    },
    "PD": {
        "Sun": "Next few weeks: decisive entries in leaders are favoured.",
        "Moon": "Next few weeks: mood-driven moves — fade extremes, keep size modest.",
        "Mars": "Next few weeks: volatile — quick trades, tight stops.",
        "Mercury": "Next few weeks: good for research, rebalancing and calculated short-term trades.",
        "Jupiter": "Next few weeks: supportive — add to quality on pullbacks.",
        "Venus": "Next few weeks: steady — income and accumulation strategies work.",
        "Saturn": "Next few weeks: slow — be patient, don't force trades.",
        "Rahu": "Next few weeks: whipsaw risk — halve size on new ideas.",
        "Ketu": "Next few weeks: detach — book profits, avoid new speculation.",
    },
}


def _fmt(dt: datetime) -> str:
    return dt.strftime("%d-%m-%Y")


class VimshottariDasha:
    """Compute the full Vimshottari dasha tree from the Moon's nakshatra at birth."""

    def __init__(self, moon_sidereal_longitude: float, birth_utc: datetime,
                 display_offset_hours: float = 0.0):
        """
        Args:
            moon_sidereal_longitude: Moon's sidereal longitude in degrees at birth.
            birth_utc: birth moment as an aware or naive UTC datetime.
        """
        self.birth = birth_utc if birth_utc.tzinfo is None else birth_utc.astimezone(tz=None).replace(tzinfo=None)
        self.display_offset = timedelta(hours=display_offset_hours)
        lon = moon_sidereal_longitude % 360
        span = 360.0 / 27.0
        self.nak_index = int(lon / span) % 27
        self.pada = int((lon % span) / span * 4) + 1
        frac = (lon % span) / span
        self.first_lord = NAKSHATRA_LORDS[self.nak_index]
        first_years = LORD_YEARS[self.first_lord]
        self.balance_years = first_years * (1.0 - frac)
        self.elapsed_years = first_years * frac
        logger.info(
            f"Vimshottari: nakshatra idx {self.nak_index} lord {self.first_lord}, "
            f"balance {self.balance_years:.3f}y of {first_years}y"
        )
        # Build the whole tree once
        self.tree: List[Dict] = self._build_tree()

    # ------------------------------------------------------------------
    def _md_start_lords(self) -> List[Dict]:
        """Yield (lord, years) for every mahadasha from birth, with the first one trimmed to its balance."""
        idx = LORD_ORDER.index(self.first_lord)
        out = []
        for i in range(9):
            lord = LORD_ORDER[(idx + i) % 9]
            years = self.balance_years if i == 0 else LORD_YEARS[lord]
            out.append({"lord": lord, "years": years})
        return out

    def _build_tree(self) -> List[Dict]:
        cursor = self.birth
        tree = []
        for i, md in enumerate(self._md_start_lords()):
            md_len_days = md["years"] * YEAR_DAYS
            md_start, md_end = cursor, cursor + timedelta(days=md_len_days)
            if i == 0:
                # full-length layout from the virtual (pre-birth) start, clipped at birth
                full_years = LORD_YEARS[md["lord"]]
                virtual_start = self.birth - timedelta(days=self.elapsed_years * YEAR_DAYS)
                ads = self._clip(self._antardashas(md["lord"], full_years, virtual_start), self.birth)
            else:
                ads = self._antardashas(md["lord"], md["years"], md_start)
            tree.append({
                "lord": md["lord"],
                "glyph": LORD_GLYPHS[md["lord"]],
                "start": md_start,
                "end": md_end,
                "years": round(md["years"], 3),
                "antardashas": ads,
            })
            cursor = md_end
        return tree

    def _antardashas(self, md_lord: str, md_years: float, md_start: datetime) -> List[Dict]:
        """Nine antardashas: they START with the mahadasha lord and follow Vimshottari order."""
        start_idx = LORD_ORDER.index(md_lord)
        cursor = md_start
        ads = []
        for i in range(9):
            ad_lord = LORD_ORDER[(start_idx + i) % 9]
            ad_years = md_years * (LORD_YEARS[ad_lord] / TOTAL_YEARS)
            ad_start = cursor
            ad_end = cursor + timedelta(days=ad_years * YEAR_DAYS)
            ads.append({
                "lord": ad_lord,
                "glyph": LORD_GLYPHS[ad_lord],
                "start": ad_start,
                "end": ad_end,
                "years": round(ad_years, 3),
                "pratyantardashas": self._pratyantardashas(ad_lord, ad_years, ad_start),
            })
            cursor = ad_end
        return ads

    @staticmethod
    def _clip(periods: List[Dict], birth: datetime) -> List[Dict]:
        """Drop sub-periods that ended before birth; start the running one at birth."""
        out = []
        for p in periods:
            if p["end"] <= birth:
                continue
            q = dict(p)
            if q["start"] < birth:
                q["start"] = birth
                q["years"] = round((q["end"] - birth).days / YEAR_DAYS, 4)
                q["balance_at_birth"] = True
                if "pratyantardashas" in q:
                    q["pratyantardashas"] = VimshottariDasha._clip(q["pratyantardashas"], birth)
            out.append(q)
        return out

    def _pratyantardashas(self, ad_lord: str, ad_years: float, ad_start: datetime) -> List[Dict]:
        start_idx = LORD_ORDER.index(ad_lord)
        cursor = ad_start
        pds = []
        for i in range(9):
            pd_lord = LORD_ORDER[(start_idx + i) % 9]
            pd_years = ad_years * (LORD_YEARS[pd_lord] / TOTAL_YEARS)
            pd_start = cursor
            pd_end = cursor + timedelta(days=pd_years * YEAR_DAYS)
            pds.append({"lord": pd_lord, "glyph": LORD_GLYPHS[pd_lord],
                        "start": pd_start, "end": pd_end, "years": round(pd_years, 4)})
            cursor = pd_end
        return pds

    # ------------------------------------------------------------------
    def current(self, when: Optional[datetime] = None) -> Dict:
        """Locate MD / AD / PD containing `when` (default now)."""
        when = when or datetime.now()
        for md in self.tree:
            if md["start"] <= when < md["end"]:
                for ad in md["antardashas"]:
                    if ad["start"] <= when < ad["end"]:
                        for pd_ in ad["pratyantardashas"]:
                            if pd_["start"] <= when < pd_["end"]:
                                return {
                                    "mahadasha": md, "antardasha": ad, "pratyantardasha": pd_,
                                    "when": when,
                                }
                        return {"mahadasha": md, "antardasha": ad, "pratyantardasha": None, "when": when}
        # before birth / beyond 120y
        return {"mahadasha": None, "antardasha": None, "pratyantardasha": None, "when": when}

    # ------------------------------------------------------------------
    def _d(self, dt: datetime) -> str:
        """dd-mm-yyyy in the native's local (birth) time zone."""
        return _fmt(dt + self.display_offset)

    def serialize(self, upto_ad: bool = True) -> Dict:
        """JSON-safe tree (dates as dd-mm-yyyy strings in local birth time)."""
        _fmt = self._d  # noqa: N806 — shadow the module helper with the tz-aware one
        out_mds = []
        for md in self.tree:
            ads = []
            if upto_ad:
                for ad in md["antardashas"]:
                    ads.append({
                        "lord": ad["lord"], "glyph": ad["glyph"],
                        "start": _fmt(ad["start"]), "end": _fmt(ad["end"]),
                        "years": ad["years"],
                        "balance_at_birth": ad.get("balance_at_birth", False),
                        "pratyantardashas": [
                            {"lord": p["lord"], "glyph": p["glyph"], "start": _fmt(p["start"]),
                             "end": _fmt(p["end"]), "years": p["years"],
                             "balance_at_birth": p.get("balance_at_birth", False)}
                            for p in ad["pratyantardashas"]
                        ],
                    })
            out_mds.append({
                "lord": md["lord"], "glyph": md["glyph"],
                "start": _fmt(md["start"]), "end": _fmt(md["end"]),
                "years": md["years"], "antardashas": ads,
            })
        return {
            "moon_nakshatra_index": self.nak_index,
            "pada": self.pada,
            "first_lord": self.first_lord,
            "balance_years": round(self.balance_years, 3),
            "elapsed_years_at_birth": round(self.elapsed_years, 3),
            "year_days": YEAR_DAYS,
            "mahadashas": out_mds,
        }

    def trading_now(self, when: Optional[datetime] = None) -> Dict:
        """Current MD / AD / PD with dates and a one-line trading meaning for each level."""
        cur = self.current(when)
        out = {}
        for key, lvl in (("mahadasha", "MD"), ("antardasha", "AD"), ("pratyantardasha", "PD")):
            p = cur.get(key)
            out[key] = None if not p else {
                "lord": p["lord"], "start": self._d(p["start"]), "end": self._d(p["end"]),
                "years": p["years"], "meaning": TRADING_LINES[lvl][p["lord"]],
            }
        return out

    def interpretation(self, when: Optional[datetime] = None) -> Dict:
        cur = self.current(when)
        md, ad, pd_ = cur["mahadasha"], cur["antardasha"], cur["pratyantardasha"]
        if not md:
            return {"headline": "Outside the 120-year Vimshottari span", "detail": ""}
        combo = f"{md['lord']} mahadasha · {ad['lord']} antardasha"
        return {
            "headline": combo,
            "detail": (
                f"{DASHA_INTERPRETATIONS[md['lord']]} Within it, the {ad['lord']} sub-period "
                f"({_fmt(ad['start'])} – {_fmt(ad['end'])}) colours the tone: "
                f"{LORD_THEMES[ad['lord']]}."
            ),
            "md_theme": DASHA_INTERPRETATIONS[md["lord"]],
            "ad_theme": LORD_THEMES[ad["lord"]],
        }


def demo_check():
    """Self-test: the nine antardashas of every mahadasha must sum to the MD length."""
    moon = 133.0  # ~ Leo 13° -> Magha nakshatra (Ketu)
    v = VimshottariDasha(moon, datetime(1990, 1, 1))
    ok = True
    for md in v.tree:
        s = sum(a["years"] for a in md["antardashas"])
        if abs(s - md["years"]) > 0.01:  # display values are rounded to 3dp
            ok = False
            print(f"FAIL {md['lord']}: ads sum {s} != md {md['years']}")
        first_ad = md["antardashas"][0]["lord"]
        if first_ad != md["lord"] and md is not v.tree[0]:
            ok = False
            print(f"FAIL {md['lord']}: first AD {first_ad} != MD lord")
        # exact date-chain check: last AD must end exactly at MD end
        last_ad_end = md["antardashas"][-1]["end"]
        md_end = md["end"]
        if abs((last_ad_end - md_end).days) > 1:
            ok = False
            print(f"FAIL {md['lord']}: last AD end {last_ad_end} vs MD end {md_end}")
    print("Antardasha invariants:", "PASS" if ok else "FAIL")
    cur = v.current()
    print("Now:", cur["mahadasha"]["lord"], "/", cur["antardasha"]["lord"], "/", cur["pratyantardasha"]["lord"])
    return ok


if __name__ == "__main__":
    demo_check()
