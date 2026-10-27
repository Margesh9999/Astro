"""
Classical data tables for the Astro Analysis master engine.

Sources: BPHS (Brihat Parashara Hora Shastra), Jaimini Sutras, KP readers,
Nakshatra Karma Vipaka Samhita — mirroring the uploaded "Astro Analysis" guide.

Ashtakvarga prastara (bindu) tables are the standard BPHS ones. Per-contributor
totals before reduction: Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56,
Venus 52, Saturn 39, Lagna 60 → 397 shashtiamsa-points; after Trikona +
Ekadhipatya shodhana the Sarvashtakavarga always totals the canonical 337.
"""

# ---------------------------------------------------------------------------
# 27 Nakshatras — (name, lord, deity, symbol, karmic theme)
# ---------------------------------------------------------------------------
NAKSHATRAS = [
    ("Ashwini", "Ketu", "Ashwini Kumaras", "Horse head", "Healing, swift karmic push, new beginnings"),
    ("Bharani", "Venus", "Yama", "Yoni", "Transformation, birth-death, restraint"),
    ("Krittika", "Sun", "Agni", "Razor/flame", "Cutting, purification, nourishment"),
    ("Rohini", "Moon", "Brahma", "Ox cart", "Growth, creativity, charm"),
    ("Mrigashira", "Mars", "Soma", "Deer head", "Searching, curiosity, beauty"),
    ("Ardra", "Rahu", "Rudra", "Teardrop", "Storm, intensity, destruction and renewal"),
    ("Punarvasu", "Jupiter", "Aditi", "Quiver", "Return, renewal, wisdom"),
    ("Pushya", "Saturn", "Brihaspati", "Cow udder", "Nourishment, protection, auspiciousness"),
    ("Ashlesha", "Mercury", "Nagas", "Coiled serpent", "Kundalini, cunning, deep insight"),
    ("Magha", "Ketu", "Pitris", "Throne", "Ancestors, royalty, authority"),
    ("Purva Phalguni", "Venus", "Bhaga", "Front legs of bed", "Enjoyment, creativity, union"),
    ("Uttara Phalguni", "Sun", "Aryaman", "Back legs of bed", "Service, contracts, marriage"),
    ("Hasta", "Moon", "Savitar", "Hand", "Skill, hands, manifestation"),
    ("Chitra", "Mars", "Tvashtar", "Jewel", "Architecture, art, brilliance"),
    ("Swati", "Rahu", "Vayu", "Young shoot", "Independence, wind, movement"),
    ("Vishakha", "Jupiter", "Indra-Agni", "Triumphal arch", "Ambition, duality, focus"),
    ("Anuradha", "Saturn", "Mitra", "Lotus", "Devotion, friendship, discipline"),
    ("Jyeshtha", "Mercury", "Indra", "Earring/umbrella", "Seniority, protection, occult"),
    ("Mula", "Ketu", "Nirriti", "Roots", "Roots, destruction, research"),
    ("Purva Ashadha", "Venus", "Apah", "Fan/winnowing basket", "Invigoration, victory, water"),
    ("Uttara Ashadha", "Sun", "Vishvadevas", "Elephant tusk", "Enduring victory, leadership"),
    ("Shravana", "Moon", "Vishnu", "Ear", "Listening, learning, connection"),
    ("Dhanishta", "Mars", "Vasus", "Drum", "Wealth, music, rhythm"),
    ("Shatabhisha", "Rahu", "Varuna", "Empty circle", "Healing, secrecy, large gatherings"),
    ("Purva Bhadrapada", "Jupiter", "Aja Ekapada", "Sword/front legs of bed", "Spiritual fire, transformation"),
    ("Uttara Bhadrapada", "Saturn", "Ahirbudhnya", "Back legs of bed", "Depth, wisdom, final release"),
    ("Revati", "Mercury", "Pushan", "Fish/drum", "Nourishment, completion, travel"),
]

NAK_NAMES = [n[0] for n in NAKSHATRAS]

# ---------------------------------------------------------------------------
# Vimshottari scaffolding (shared with dasha.py — kept in sync)
# ---------------------------------------------------------------------------
VIM_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
VIM_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
             "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}

# ---------------------------------------------------------------------------
# Yogini dasha — 36-year cycle (name, years, ruling graha, money meaning)
# ---------------------------------------------------------------------------
YOGINIS = [
    ("Mangala", 1, "Moon", "liquidity and public-mood cycles; consumer & FMCG money flows well"),
    ("Pingala", 2, "Sun", "authority and government-linked gains; energy and PSU names reward patience"),
    ("Dhanya", 3, "Jupiter", "the best yogini for wealth — banking, education and compounding flourish"),
    ("Bhramari", 4, "Mars", "fast, aggressive money cycles; metals, energy and momentum trades"),
    ("Bhadrika", 5, "Mercury", "trade, analysis and technology gains; best for systematic strategies"),
    ("Ulka", 6, "Saturn", "a grinding stretch — slow systematic accumulation, avoid leverage"),
    ("Siddha", 7, "Venus", "accomplishment and comfort money; luxury, finance and partnerships rally"),
    ("Sankata", 8, "Rahu", "obstacles and volatility — speculation bites, keep stops tight and size small"),
]
YOGINI_TOTAL = sum(y[1] for y in YOGINIS)  # 36

# ---------------------------------------------------------------------------
# Jaimini chara karakas (7-karaka scheme) — (key, label, money meaning)
# ---------------------------------------------------------------------------
CHARA_KARAKAS = [
    ("AK", "Atmakaraka", "soul planet — sets your deepest money purpose and the lesson wealth must teach you"),
    ("AmK", "Amatyakaraka", "career planet — guides the profession and market style through which money actually arrives"),
    ("BK", "Bhratrikaraka", "courage & siblings — co-founders, peer networks and bold calculated bets"),
    ("MK", "Matrikaraka", "home & mother — property, domestic stability and the emotional base of risk appetite"),
    ("PK", "Putrakaraka", "children & creativity — speculation (5th house) themes and legacy investing"),
    ("GK", "Gnatikaraka", "obstacles & competition — rivals, litigation risk and where losses can ambush you"),
    ("DK", "Darakaraka", "spouse & partnership — joint capital, advisory partners and client-facing gains"),
]

# ---------------------------------------------------------------------------
# Sign lords, natures, friendship (natural relationships, BPHS)
# ---------------------------------------------------------------------------
SIGN_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
              "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]

NATURAL_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}   # waxing Moon treated benefic
NATURAL_MALEFICS = {"Saturn", "Mars", "Sun", "Rahu", "Ketu"}  # waning Moon treated malefic

FRIENDS = {
    "Sun": {"Moon", "Mars", "Jupiter"}, "Moon": {"Sun", "Mercury"}, "Mars": {"Sun", "Moon", "Jupiter"},
    "Mercury": {"Sun", "Venus"}, "Jupiter": {"Sun", "Moon", "Mars"}, "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
}
ENEMIES = {
    "Sun": {"Venus", "Saturn"}, "Moon": set(), "Mars": {"Mercury"}, "Mercury": {"Moon"},
    "Jupiter": {"Mercury", "Venus"}, "Venus": {"Sun", "Moon"}, "Saturn": {"Sun", "Moon", "Mars"},
}

# Deep-exaltation points (absolute sidereal longitude)
EXALT_ABS = {"Sun": 10.0, "Moon": 33.0, "Mercury": 165.0, "Venus": 357.0,
             "Mars": 298.0, "Jupiter": 95.0, "Saturn": 200.0}

# Minimum shadbala in Rupas (BPHS standard, approximate)
SHADBALA_REQUIRED = {"Sun": 6.45, "Moon": 5.14, "Mars": 4.90, "Mercury": 6.50,
                     "Jupiter": 6.45, "Venus": 5.50, "Saturn": 5.50}

NAISARGIKA = {"Sun": 60.0, "Moon": 51.43, "Venus": 42.86, "Jupiter": 34.29,
              "Mercury": 25.71, "Mars": 17.14, "Saturn": 8.57}

MEAN_SPEED = {"Sun": 0.9856, "Moon": 13.176, "Mercury": 1.383, "Venus": 1.200,
              "Mars": 0.524, "Jupiter": 0.083, "Saturn": 0.0345}

COMBUST_ORB = {"Moon": 12.0, "Mercury": 14.0, "Venus": 10.0, "Mars": 17.0,
               "Jupiter": 11.0, "Saturn": 15.0}

WEEKDAY_LORDS = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]  # Mon..Sun
# python weekday(): Mon=0 .. Sun=6 — Monday is ruled by the Moon, Sunday by the Sun.

CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# ---------------------------------------------------------------------------
# Ashtakvarga prastara tables — BPHS Chapter 66 (verified against the jyotish
# library sources + K.N. Rao/B.V. Raman printings).
# Per-contributor totals (classical, chart-invariant):
#   Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56, Venus 52, Saturn 39
#   -> Sarvashtakavarga (7 planets) = 337 exactly; Lagna's own BAV = 49
#      (supplementary, counted separately).
# beneficiary: which planet's BAV; reference: counted FROM which body/Asc.
# Values are house-distances (1..N) that RECEIVE a bindu.
# ---------------------------------------------------------------------------
ASHTAKVARGA = {
    "Sun": {
        "Sun": [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon": [3, 6, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus": [6, 7, 12],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Asc": [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun": [3, 6, 7, 8, 10, 11],
        "Moon": [1, 3, 6, 7, 9, 10, 11],
        "Mars": [2, 3, 5, 6, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 2, 4, 7, 8, 10, 11],
        "Venus": [3, 4, 5, 7, 9, 10, 11],
        "Saturn": [3, 5, 6, 11],
        "Asc": [3, 6, 10, 11],
    },
    "Mars": {
        "Sun": [3, 5, 6, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus": [6, 8, 11, 12],
        "Saturn": [1, 4, 7, 8, 9, 10, 11],
        "Asc": [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun": [5, 6, 9, 11, 12],
        "Moon": [2, 4, 6, 8, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Asc": [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon": [2, 5, 7, 9, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus": [2, 5, 6, 9, 10, 11],
        "Saturn": [3, 5, 6, 12],
        "Asc": [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun": [8, 11, 12],
        "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars": [3, 4, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn": [3, 4, 5, 8, 9, 10, 11],
        "Asc": [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun": [1, 2, 4, 7, 8, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus": [6, 11, 12],
        "Saturn": [3, 5, 6, 11],
        "Asc": [1, 3, 4, 6, 10, 11],
    },
    # Lagna's own BAV — supplementary (not part of the 337 SAV)
    "Asc": {
        "Sun": [3, 4, 6, 10, 11, 12],
        "Moon": [3, 6, 10, 11, 12],
        "Mars": [1, 3, 6, 10, 11],
        "Mercury": [1, 2, 4, 6, 8, 10, 11],
        "Jupiter": [1, 2, 4, 5, 6, 7, 9, 10, 11],
        "Venus": [1, 2, 3, 4, 5, 8, 9],
        "Saturn": [1, 3, 4, 6, 10, 11],
        "Asc": [3, 6, 10, 11],
    },
}

# Classical per-contributor totals (prastara, before reduction)
BAV_TOTALS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
              "Jupiter": 56, "Venus": 52, "Saturn": 39, "Asc": 49}

# Sign pairs owned by the same graha (for Ekadhipatya shodhana)
DUAL_OWNERS = [("Aries", "Scorpio", "Mars"), ("Taurus", "Libra", "Venus"),
               ("Gemini", "Virgo", "Mercury"), ("Sagittarius", "Pisces", "Jupiter"),
               ("Capricorn", "Aquarius", "Saturn")]

TRIKONA_GROUPS = [[0, 4, 8], [1, 5, 9], [2, 6, 10], [3, 7, 11]]  # 0-indexed sign trios
