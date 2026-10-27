"""
Astrological aspects calculations
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class AspectsCalculator:
    """Calculate astrological aspects between planets"""

    # Major aspects with their angles and orbs
    ASPECTS = {
        "conjunction": {"angle": 0, "orb": 8},
        "opposition": {"angle": 180, "orb": 8},
        "trine": {"angle": 120, "orb": 8},
        "square": {"angle": 90, "orb": 8},
        "sextile": {"angle": 60, "orb": 6},
        "quincunx": {"angle": 150, "orb": 4},
        "semi-sextile": {"angle": 30, "orb": 2},
        "semi-square": {"angle": 45, "orb": 2},
        "sesqui-square": {"angle": 135, "orb": 2}
    }

    def __init__(self):
        pass

    def calculate_angle_difference(self, pos1: float, pos2: float) -> float:
        """
        Calculate the shortest angular distance between two positions

        Args:
            pos1: First position in degrees (0-360)
            pos2: Second position in degrees (0-360)

        Returns:
            Angle difference in degrees (0-180)
        """
        diff = abs(pos1 - pos2) % 360
        return min(diff, 360 - diff)

    def calculate_aspect(
        self,
        planet1_pos: float,
        planet2_pos: float,
        planet1_name: str = "",
        planet2_name: str = ""
    ) -> Optional[Dict]:
        """
        Calculate if two planets form an aspect

        Args:
            planet1_pos: First planet's longitude
            planet2_pos: Second planet's longitude
            planet1_name: Name of first planet (optional)
            planet2_name: Name of second planet (optional)

        Returns:
            Dictionary with aspect information or None if no aspect
        """
        angle_diff = self.calculate_angle_difference(planet1_pos, planet2_pos)

        for aspect_name, aspect_data in self.ASPECTS.items():
            angle = aspect_data["angle"]
            orb = aspect_data["orb"]

            # Check if the angle difference is within the orb
            if abs(angle_diff - angle) <= orb:
                # Calculate applying/separating (simplified)
                # In a full implementation, we'd need planetary speeds
                is_applying = True  # Placeholder

                return {
                    "aspect": aspect_name,
                    "angle_exact": angle,
                    "angle_actual": angle_diff,
                    "orb_used": abs(angle_diff - angle),
                    "planet1": planet1_name,
                    "planet2": planet2_name,
                    "is_applying": is_applying,
                    "strength": max(0, 1 - (abs(angle_diff - angle) / orb))  # 0 to 1
                }

        return None

    def calculate_all_aspects(
        self,
        planet_positions: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Calculate all aspects between all planets

        Args:
            planet_positions: Dictionary of planet positions from ephemeris

        Returns:
            List of aspect dictionaries
        """
        aspects = []
        planet_names = list(planet_positions.keys())

        for i, planet1 in enumerate(planet_names):
            for planet2 in planet_names[i+1:]:
                pos1 = planet_positions[planet1]["longitude"]
                pos2 = planet_positions[planet2]["longitude"]

                aspect = self.calculate_aspect(
                    pos1, pos2, planet1, planet2
                )

                if aspect:
                    aspects.append(aspect)

        return aspects

    def get_aspect_score(
        self,
        aspects: List[Dict],
        aspect_type: str = None
    ) -> float:
        """
        Calculate a composite score based on aspects

        Args:
            aspects: List of aspect dictionaries
            aspect_type: Specific aspect type to score (optional)

        Returns:
            Composite aspect score
        """
        if not aspects:
            return 0.0

        if aspect_type:
            relevant_aspects = [a for a in aspects if a["aspect"] == aspect_type]
        else:
            relevant_aspects = aspects

        if not relevant_aspects:
            return 0.0

        # Weight different aspects differently
        aspect_weights = {
            "conjunction": 1.0,
            "opposition": 0.8,
            "trine": 0.6,
            "square": 0.7,
            "sextile": 0.4,
            "quincunx": 0.2,
            "semi-sextile": 0.1,
            "semi-square": 0.15,
            "sesqui-square": 0.15
        }

        total_score = 0.0
        for aspect in relevant_aspects:
            weight = aspect_weights.get(aspect["aspect"], 0.1)
            strength = aspect["strength"]
            total_score += weight * strength

        return total_score