"""
Vedic astrology calculations
"""
import swisseph as swe
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class VedicCalculator:
    """Vedic (sidereal) astrology calculations"""

    # Nakshatras (lunar mansions) - 27 divisions of 13°20' each
    NAKSHATRAS = [
        "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
        "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
        "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
        "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
        "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
    ]

    # Tithis (lunar days) - 30 divisions
    TITHIS = [
        "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
        "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
        "Trayodashi", "Chaturdashi", "Purnima", "Pratipada", "Dwitiya", "Tritiya",
        "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami",
        "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Amavasya"
    ]

    def __init__(self, ayanamsa_mode: int = swe.SIDM_LAHIRI):
        """
        Initialize Vedic calculator

        Args:
            ayanamsa_mode: Swiss Ephemeris ayanamsa mode (default: Lahiri)
        """
        self.ayanamsa_mode = ayanamsa_mode
        swe.set_sid_mode(self.ayanamsa_mode)
        logger.info(f"Vedic calculator initialized with ayanamsa mode: {ayanamsa_mode}")

    def get_ayanamsa(self, julian_day: float) -> float:
        """
        Get the ayanamsa value for a given Julian day

        Args:
            julian_day: Julian day number

        Returns:
            Ayanamsa value in degrees
        """
        return swe.get_ayanamsa_ut(julian_day)

    def tropical_to_sidereal(self, tropical_longitude: float, julian_day: float) -> float:
        """
        Convert tropical longitude to sidereal (Vedic) longitude

        Args:
            tropical_longitude: Tropical longitude in degrees
            julian_day: Julian day number

        Returns:
            Sidereal longitude in degrees
        """
        ayanamsa = self.get_ayanamsa(julian_day)
        sidereal_longitude = tropical_longitude - ayanamsa
        # Normalize to 0-360
        return sidereal_longitude % 360

    def calculate_nakshatra(self, sidereal_longitude: float) -> Dict:
        """
        Calculate nakshatra (lunar mansion) from sidereal longitude

        Args:
            sidereal_longitude: Sidereal longitude in degrees

        Returns:
            Dictionary with nakshatra information
        """
        # Each nakshatra is 13°20' (13.333... degrees)
        sidereal_longitude = sidereal_longitude % 360
        nakshatra_width = 360 / 27
        nakshatra_index = int(sidereal_longitude / nakshatra_width) % 27

        # Position within nakshatra (0 to 1)
        position_in_nakshatra = (sidereal_longitude % nakshatra_width) / nakshatra_width

        # Pada (quarter) of nakshatra (1-4)
        pada = int(position_in_nakshatra * 4) + 1

        return {
            "nakshatra": self.NAKSHATRAS[nakshatra_index],
            "nakshatra_index": nakshatra_index,
            "pada": pada,
            "position_in_nakshatra": position_in_nakshatra
        }

    def calculate_tithi(self, moon_longitude: float, sun_longitude: float, julian_day: float) -> Dict:
        """
        Calculate tithi (lunar day) from moon and sun longitudes

        Args:
            moon_longitude: Moon's sidereal longitude
            sun_longitude: Sun's sidereal longitude
            julian_day: Julian day number

        Returns:
            Dictionary with tithi information
        """
        # Calculate angular distance between moon and sun
        diff = (moon_longitude - sun_longitude) % 360

        # Each tithi is 12 degrees (360/30)
        tithi_width = 12
        tithi_index = int(diff / tithi_width)

        # Position within tithi (0 to 1)
        position_in_tithi = (diff % tithi_width) / tithi_width

        return {
            "tithi": self.TITHIS[tithi_index],
            "tithi_index": tithi_index,
            "position_in_tithi": position_in_tithi,
            "is_shukla_paksha": tithi_index < 15,  # Waxing phase
            "paksha": "Shukla" if tithi_index < 15 else "Krishna"  # Waxing/Waning
        }

    def calculate_planet_position_vedic(
        self,
        planet: int,
        julian_day: float
    ) -> Dict[str, float]:
        """
        Calculate Vedic (sidereal) position of a planet

        Args:
            planet: Swiss Ephemeris planet constant
            julian_day: Julian day number

        Returns:
            Dictionary with Vedic planetary data
        """
        # First get tropical position
        pos, ret = swe.calc_ut(julian_day, planet)
        tropical_longitude = pos[0]
        latitude = pos[1]
        distance = pos[2]
        speed_lon = pos[3]
        speed_lat = pos[4]
        speed_dist = pos[5]

        # Convert to sidereal
        sidereal_longitude = self.tropical_to_sidereal(tropical_longitude, julian_day)

        # Calculate zodiac sign and degree within sign (sidereal)
        sign_number = int(sidereal_longitude / 30)
        degree_within_sign = sidereal_longitude % 30

        # Vedic zodiac signs (same as Western but starting from different point)
        signs = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]

        # Calculate nakshatra
        nakshatra_data = self.calculate_nakshatra(sidereal_longitude)

        return {
            "longitude": sidereal_longitude,
            "tropical_longitude": tropical_longitude,
            "latitude": latitude,
            "distance": distance,
            "speed_longitude": speed_lon,
            "speed_latitude": speed_lat,
            "speed_distance": speed_dist,
            "sign": signs[sign_number],
            "sign_number": sign_number,
            "degree_within_sign": degree_within_sign,
            "is_retrograde": speed_lon < 0,
            "nakshatra": nakshatra_data["nakshatra"],
            "nakshatra_index": nakshatra_data["nakshatra_index"],
            "pada": nakshatra_data["pada"],
            "ayanamsa": self.get_ayanamsa(julian_day)
        }

    def calculate_all_planets_vedic(self, julian_day: float) -> Dict[str, Dict]:
        """
        Calculate Vedic positions for all major planets

        Args:
            julian_day: Julian day number

        Returns:
            Dictionary with planet names as keys and Vedic position data as values
        """
        planets = {
            "Sun": swe.SUN,
            "Moon": swe.MOON,
            "Mercury": swe.MERCURY,
            "Venus": swe.VENUS,
            "Mars": swe.MARS,
            "Jupiter": swe.JUPITER,
            "Saturn": swe.SATURN,
            "Uranus": swe.URANUS,
            "Neptune": swe.NEPTUNE,
            "Pluto": swe.PLUTO
        }

        results = {}
        for name, planet_id in planets.items():
            try:
                results[name] = self.calculate_planet_position_vedic(planet_id, julian_day)
            except Exception as e:
                logger.warning(f"Could not calculate Vedic position for {name}: {e}")

        return results

# ---------------------------------------------------------------------------
# v1.3 — one correct, configurable sidereal pipeline used by the jataka engine,
# /natal and /planetary. Positions come straight from swe.calc_ut with
# FLG_SIDEREAL | FLG_SPEED (no manual "tropical − ayanamsa" subtraction), and the
# Lagna from swe.houses_ex with the same sidereal flag + mode.
# ---------------------------------------------------------------------------
SIGN_NAMES = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
              "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

AYANAMSA_MODES = {
    "lahiri": (swe.SIDM_LAHIRI, "Lahiri (Chitrapaksha)"),
    "raman": (swe.SIDM_RAMAN, "B.V. Raman"),
    "kp": (swe.SIDM_KRISHNAMURTI, "Krishnamurti (KP)"),
    "tropical": (None, "Tropical (Western, no ayanamsa)"),
}
NODE_TYPES = {"mean": swe.MEAN_NODE, "true": swe.TRUE_NODE}
GRAHA_IDS = {"Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
             "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN}
# classical combustion orbs (degrees from the Sun); Mercury/Venus tighter when retrograde
COMBUST_ORBS = {"Mars": 17, "Mercury": 14, "Venus": 10, "Jupiter": 11, "Saturn": 15}
COMBUST_ORBS_RETRO = {"Mercury": 12, "Venus": 8}

_NAK_W = 360.0 / 27.0


@contextmanager
def sidereal_mode(mode: Optional[int]):
    """Temporarily set the process-global swisseph sidereal mode; ALWAYS restores Lahiri.

    ``swe.set_sid_mode`` is global state shared by every module in the process, so any
    non-default ayanamsa must be scoped — otherwise later calls silently shift by the
    ayanamsa difference (days of error on ingress dates)."""
    try:
        if mode is not None:
            swe.set_sid_mode(mode, 0, 0)
        yield
    finally:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)


def _nak(lon: float) -> Dict:
    lon %= 360.0
    i = int(lon / _NAK_W) % 27
    frac = (lon % _NAK_W) / _NAK_W
    return {"nakshatra": VedicCalculator.NAKSHATRAS[i], "nakshatra_index": i,
            "pada": int(frac * 4) + 1, "position_in_nakshatra": frac}


def _row(lon: float, speed: float, lat: float = 0.0) -> Dict:
    lon %= 360.0
    sn = int(lon // 30)
    return {"longitude": lon, "sign": SIGN_NAMES[sn], "sign_number": sn,
            "degree_within_sign": lon % 30, "speed_longitude": speed, "latitude": lat,
            "is_retrograde": speed < 0, **_nak(lon)}


def sky_positions(jd_ut: float, ayanamsa: str = "lahiri", node: str = "mean",
                  lat: Optional[float] = None, lon: Optional[float] = None,
                  outer: bool = False) -> Dict:
    """Sidereal (or tropical) positions of the nine grahas (+ optional outer planets)
    and — when an observer lat/lon is given — the Lagna, at ``jd_ut``.

    Returns {"positions": {...}, "ayanamsa": deg, "ayanamsa_label": str, "flags": int}.
    """
    mode, label = AYANAMSA_MODES.get(ayanamsa, AYANAMSA_MODES["lahiri"])
    with sidereal_mode(mode):
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        if mode is not None:
            flags |= swe.FLG_SIDEREAL
            ayan = swe.get_ayanamsa_ut(jd_ut)
        else:
            ayan = 0.0
        ids = dict(GRAHA_IDS)
        if outer:
            ids.update({"Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO})
        out: Dict[str, Dict] = {}
        for name, pid in ids.items():
            r = swe.calc_ut(jd_ut, pid, flags)[0]
            out[name] = _row(r[0], r[3], r[1])
        r = swe.calc_ut(jd_ut, NODE_TYPES.get(node, swe.MEAN_NODE), flags)[0]
        out["Rahu"] = _row(r[0], r[3])
        out["Ketu"] = _row(r[0] + 180.0, r[3])
        # nodes are always shown retrograde in Jyotish (mean node strictly is)
        out["Rahu"]["is_retrograde"] = out["Ketu"]["is_retrograde"] = True
        if lat is not None and lon is not None:
            hflags = swe.FLG_SIDEREAL if mode is not None else 0
            _cusps, ascmc = swe.houses_ex(jd_ut, float(lat), float(lon), b"W", hflags)
            asc = _row(ascmc[0], 0.0)
            asc["is_retrograde"] = False
            out["Lagna"] = asc
        # combustion (asta) — within the classical orb of the Sun
        sun = out["Sun"]["longitude"]
        for name, orb in COMBUST_ORBS.items():
            if name not in out:
                continue
            if out[name]["is_retrograde"] and name in COMBUST_ORBS_RETRO:
                orb = COMBUST_ORBS_RETRO[name]
            sep = abs((out[name]["longitude"] - sun + 180.0) % 360.0 - 180.0)
            out[name]["combust"] = bool(sep <= orb)
            out[name]["sun_separation"] = round(sep, 2)
    return {"positions": out, "ayanamsa": ayan, "ayanamsa_label": label, "flags": flags}
