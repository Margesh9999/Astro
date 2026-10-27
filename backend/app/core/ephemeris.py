"""
Planetary position calculations using Swiss Ephemeris
"""
import swisseph as swe
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class EphemerisCalculator:
    """Calculate planetary positions using Swiss Ephemeris"""

    def __init__(self, ephe_path: str = ""):
        """
        Initialize the ephemeris calculator

        Args:
            ephe_path: Path to Swiss Ephemeris files (empty for default)
        """
        if ephe_path:
            swe.set_ephe_path(ephe_path)
        logger.info("Swiss Ephemeris initialized")

    def calculate_planet_position(
        self,
        planet: int,
        julian_day: float
    ) -> Dict[str, float]:
        """
        Calculate position of a single planet

        Args:
            planet: Swiss Ephemeris planet constant
            julian_day: Julian day number

        Returns:
            Dictionary with planetary data
        """
        try:
            # Calculate position and speed
            pos, ret = swe.calc_ut(julian_day, planet)

            longitude = pos[0]  # ecliptic longitude
            latitude = pos[1]   # ecliptic latitude
            distance = pos[2]   # distance in AU
            speed_lon = pos[3]  # speed in longitude
            speed_lat = pos[4]  # speed in latitude
            speed_dist = pos[5] # speed in distance

            # Calculate zodiac sign and degree within sign
            sign_number = int(longitude / 30)
            degree_within_sign = longitude % 30

            # Zodiac signs (0=Aries, 1=Taurus, ..., 11=Pisces)
            signs = [
                "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
            ]

            return {
                "longitude": longitude,
                "latitude": latitude,
                "distance": distance,
                "speed_longitude": speed_lon,
                "speed_latitude": speed_lat,
                "speed_distance": speed_dist,
                "sign": signs[sign_number],
                "sign_number": sign_number,
                "degree_within_sign": degree_within_sign,
                "is_retrograde": speed_lon < 0
            }
        except Exception as e:
            logger.error(f"Error calculating planet position: {e}")
            raise

    def calculate_all_planets(self, julian_day: float) -> Dict[str, Dict]:
        """
        Calculate positions for all major planets

        Args:
            julian_day: Julian day number

        Returns:
            Dictionary with planet names as keys and position data as values
        """
        # Swiss Ephemeris planet constants
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
                results[name] = self.calculate_planet_position(planet_id, julian_day)
            except Exception as e:
                logger.warning(f"Could not calculate position for {name}: {e}")

        return results

    def date_to_julian(self, dt: datetime) -> float:
        """
        Convert datetime to Julian day

        Args:
            dt: DateTime object

        Returns:
            Julian day number
        """
        return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0 + dt.second/3600.0)

    def now(self) -> float:
        """Get current Julian day"""
        return self.date_to_julian(datetime.now())