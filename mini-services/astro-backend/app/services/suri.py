"""
Suri-inspired Astro-Signal Engine
=================================
Educational reimplementation of the *concepts* popularised by financial
astrologer Mohnish Suri (AstralAlgo / astralastrologer.com):

- Planetary Timing Alerts  (reversal days, volatility spike windows)
- Lunar Mood Cycle         (market mood influenced by lunar/planetary shifts)
- Planetary Transit Models (cycle-timed decisions)
- AI + Astro N-Day Range   (support/resistance projection bands)
- Astro-Technical Composite(entry/exit signal blending price structure)

This is an original, formula-level implementation built on Swiss Ephemeris
data - it does not copy any proprietary algorithm. Educational only, with no
proven predictive value (same disclaimer philosophy as the source author).
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import swisseph as swe

from app.core.ephemeris import EphemerisCalculator
from app.core.vedic import VedicCalculator

logger = logging.getLogger(__name__)

# Classical lookup tables ----------------------------------------------------
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
         "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

# speed sign-flip watchers: (planet natal constant, reversal weight, orb days)
STATION_WATCH = {
    "Mercury": (swe.MERCURY, 3.0, 2),
    "Venus": (swe.VENUS, 2.5, 2),
    "Mars": (swe.MARS, 2.0, 3),
    "Jupiter": (swe.JUPITER, 1.5, 3),
    "Saturn": (swe.SATURN, 1.5, 3),
}
INGRESS_WATCH = {
    "Sun": (swe.SUN, 1.5, 1),
    "Mercury": (swe.MERCURY, 1.5, 1),
    "Venus": (swe.VENUS, 1.5, 1),
    "Mars": (swe.MARS, 1.5, 1),
    "Jupiter": (swe.JUPITER, 2.0, 2),
    "Saturn": (swe.SATURN, 2.0, 2),
    "Rahu": ("mean_node", 1.5, 2),
}
HARD_ASPECT_ANGLES = [0, 45, 90, 135, 180, 225, 270, 315]


class SuriSignalEngine:
    """Composite astro-signal engine (educational implementation)."""

    def __init__(self, ephe_path: str = ""):
        self.eph = EphemerisCalculator(ephe_path=ephe_path)
        self.vedic = VedicCalculator(ayanamsa_mode=swe.SIDM_LAHIRI)

    # ------------------------------------------------------------------
    # low-level sky helpers
    # ------------------------------------------------------------------
    def _jd(self, date: str) -> float:
        d = datetime.strptime(date, "%Y-%m-%d")
        return swe.julday(d.year, d.month, d.day, 12.0)  # noon UT

    def _tropical_lon(self, jd: float, planet) -> float:
        pos, _ = swe.calc_ut(jd, planet, flags=swe.FLG_MOSEPH | swe.FLG_SPEED)
        return pos[0], pos[3]

    def _sidereal_lon(self, jd: float, planet) -> float:
        lon, speed = self._tropical_lon(jd, planet)
        # sid mode is process-global and other modules switch it (KP/Raman charts):
        # pin Lahiri right before reading the ayanamsa so ingress dates stay stable
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        ayan = swe.get_ayanamsa_ut(jd)
        return (lon - ayan) % 360.0, speed

    def _moon_phase_angle(self, jd: float) -> float:
        sun, _ = self._tropical_lon(jd, swe.SUN)
        moon, _ = self._tropical_lon(jd, swe.MOON)
        return (moon - sun) % 360.0

    def _moon_speed(self, jd: float) -> float:
        _, speed = self._tropical_lon(jd, swe.MOON)
        return speed

    def _retrograde_count(self, jd: float) -> int:
        n = 0
        for pl, (const, _, _) in STATION_WATCH.items():
            _, sp = self._tropical_lon(jd, const)
            if sp < 0:
                n += 1
        return n

    # ------------------------------------------------------------------
    # scores for a single date
    # ------------------------------------------------------------------
    def reversal_score(self, date: str) -> Dict:
        """Score 0-100: how 'reversal-prone' this session looks classically."""
        jd = self._jd(date)
        score = 0.0
        drivers: List[Dict] = []

        # 1) lunar hard aspects (moon-sun angle near hard division of circle)
        phase = self._moon_phase_angle(jd)
        for ang in HARD_ASPECT_ANGLES:
            diff = abs((phase - ang + 180) % 360 - 180)
            if diff <= 3.0:
                w = 2.5 if ang in (0, 90, 180, 270) else 1.5
                score += w * (1 - diff / 3.0)
                drivers.append({"type": "lunar_aspect",
                                "detail": f"Moon-Sun {ang} deg (orb {diff:.1f})",
                                "weight": round(w, 2)})
                break

        # 2) new / full moon window (±1 day)
        for d_off in (-1, 0, 1):
            p2 = self._moon_phase_angle(jd + d_off)
            if p2 <= 2.0 or p2 >= 358.0:
                score += 2.5
                drivers.append({"type": "lunation", "detail": "New Moon window", "weight": 2.5})
                break
            if 178.0 <= p2 <= 182.0:
                score += 2.5
                drivers.append({"type": "lunation", "detail": "Full Moon window", "weight": 2.5})
                break

        # 3) stations within orb
        for pl, (const, w, orb) in STATION_WATCH.items():
            for d_off in range(-orb, orb + 1):
                jd0, jd1 = jd + d_off - 0.5, jd + d_off + 0.5
                s0 = self._tropical_lon(jd0, const)[1]
                s1 = self._tropical_lon(jd1, const)[1]
                if s0 * s1 < 0:  # speed sign flip = station
                    score += w
                    kind = "retrograde station" if s1 < 0 else "direct station"
                    drivers.append({"type": "station",
                                    "detail": f"{pl} {kind} (+/-{d_off}d)", "weight": w})
                    break

        # 4) ingresses within orb
        for pl, (const, w, orb) in INGRESS_WATCH.items():
            base = self._sidereal_lon(jd, swe.MEAN_NODE if const == "mean_node" else const)[0]
            sign0 = int(base // 30)
            for d_off in range(-orb, orb + 1):
                if d_off == 0:
                    continue
                other = self._sidereal_lon(
                    jd + d_off, swe.MEAN_NODE if const == "mean_node" else const)[0]
                if int(other // 30) != sign0:
                    score += w
                    drivers.append({"type": "ingress",
                                    "detail": f"{pl} sign change (+/-{d_off}d)", "weight": w})
                    break

        pct = min(100.0, score / 12.0 * 100.0)
        return {"date": date, "reversal_score": round(pct, 1),
                "drivers": drivers}

    def volatility_score(self, date: str) -> Dict:
        """Score 0-100: classical 'volatility spike window' likelihood."""
        jd = self._jd(date)
        score = 0.0
        drivers: List[Dict] = []

        phase = self._moon_phase_angle(jd)
        if phase <= 4.0 or phase >= 356.0:
            score += 3.0
            drivers.append({"detail": "New Moon volatility window", "weight": 3.0})
        elif 176.0 <= phase <= 184.0:
            score += 3.0
            drivers.append({"detail": "Full Moon volatility window", "weight": 3.0})

        # Mars / Saturn stations are the classic squeeze triggers
        for pl in ("Mars", "Saturn"):
            const, w, orb = STATION_WATCH[pl]
            for d_off in range(-orb, orb + 1):
                s0 = self._tropical_lon(jd + d_off - 0.5, const)[1]
                s1 = self._tropical_lon(jd + d_off + 0.5, const)[1]
                if s0 * s1 < 0:
                    score += w
                    drivers.append({"detail": f"{pl} station (+/-{d_off}d)", "weight": w})
                    break

        # nodes changing sign = 18.6y cycle seam
        n0 = self._sidereal_lon(jd, swe.MEAN_NODE)[0]
        for d_off in (-1, 1):
            n1 = self._sidereal_lon(jd + d_off, swe.MEAN_NODE)[0]
            if int(n0 // 30) != int(n1 // 30):
                score += 2.0
                drivers.append({"detail": "Rahu-Ketu axis sign change", "weight": 2.0})

        # slow moon (near apogee) = indecision tape
        ms = abs(self._moon_speed(jd))
        if ms < 12.2:  # deg/day; ~12.2 is roughly the lower decile
            score += 1.0
            drivers.append({"detail": f"Slow Moon ({ms:.1f} deg/day)", "weight": 1.0})

        pct = min(100.0, score / 9.0 * 100.0)
        return {"date": date, "volatility_score": round(pct, 1), "drivers": drivers}

    # ------------------------------------------------------------------
    # market mood index (0 = extreme fear tape, 100 = euphoric tape)
    # ------------------------------------------------------------------
    def market_mood(self, date: str) -> Dict:
        jd = self._jd(date)
        components: Dict[str, float] = {}

        phase = self._moon_phase_angle(jd)
        # waxing (0..180) constructive, waning cautious; peak near full
        components["lunar_phase"] = 50 + 50 * math.cos(math.radians(phase - 180)) * 0.5 \
            if phase >= 180 else 50 + (phase / 180) * 25 - 25 * (phase / 180)
        # simpler, deterministic: waxing-> 55..85, full peak 85, waning-> 55..25
        if phase < 180:
            components["lunar_phase"] = 55 + 30 * (phase / 180.0)
        else:
            components["lunar_phase"] = 85 - 60 * ((phase - 180) / 180.0)

        retro = self._retrograde_count(jd)
        components["retro_load"] = max(0.0, 70.0 - 12.0 * retro)

        # benefic vs malefic angular placement (sidereal sign dignity proxy)
        DIGNITY = {"Jupiter": {3, 8}, "Venus": {1, 6}}       # own/exalt signs idx
        MALEFIC = {"Saturn": {9, 10}, "Mars": {0, 7}}
        bene = 0.0
        for pl, signs in DIGNITY.items():
            lon, _ = self._sidereal_lon(jd, STATION_WATCH.get(pl, (swe.JUPITER, 0, 0))[0]
                                        if pl == "Jupiter" else swe.VENUS)
            if int(lon // 30) in signs:
                bene += 15
        for pl, signs in MALEFIC.items():
            const = swe.SATURN if pl == "Saturn" else swe.MARS
            lon, _ = self._sidereal_lon(jd, const)
            if int(lon // 30) in signs:
                bene -= 12
        components["dignity"] = 50 + bene

        # tithi moon speed: fast moon = active tape
        ms = abs(self._moon_speed(jd))
        components["moon_velocity"] = 50 + (ms - 12.5) * 8.0

        for k, v in components.items():
            components[k] = round(min(100.0, max(0.0, v)), 1)

        mood = float(np.mean(list(components.values())))
        label = ("Euphoric" if mood >= 70 else "Constructive" if mood >= 58 else
                 "Neutral" if mood >= 45 else "Cautious" if mood >= 30 else "Fearful")
        return {"date": date, "mood_index": round(mood, 1), "mood_label": label,
                "phase_angle": round(phase, 1),
                "lunar": "Waxing" if phase < 180 else "Waning",
                "retrogrades": retro, "components": components}

    # ------------------------------------------------------------------
    # timing alerts for the next N days
    # ------------------------------------------------------------------
    def timing_alerts(self, start_date: str, days: int = 14) -> List[Dict]:
        alerts: List[Dict] = []
        base = datetime.strptime(start_date, "%Y-%m-%d")
        prev_phase = self._moon_phase_angle(self._jd(start_date) - 1)
        prev_signs: Dict[str, int] = {}
        prev_speed: Dict[str, float] = {}
        for pl, (const, _, _) in {**STATION_WATCH, **{"Rahu": ("mean_node", 0, 0)}}.items():
            c = swe.MEAN_NODE if const == "mean_node" else const
            lon, sp = self._sidereal_lon(self._jd(start_date) - 1, c)
            prev_signs[pl] = int(lon // 30)
            prev_speed[pl] = sp

        for i in range(days):
            date = (base + timedelta(days=i)).strftime("%Y-%m-%d")
            jd = self._jd(date)

            # lunation crossing
            ph = self._moon_phase_angle(jd)
            for name, lo, hi in (("New Moon", 355, 360), ("New Moon", 0, 5),
                                 ("Full Moon", 175, 185)):
                if lo <= ph <= hi:
                    alerts.append({"date": date, "kind": "volatility_window",
                                   "title": name,
                                   "note": f"{name} lunar window - classic vol-spike zone",
                                   "strength": 4})
                    break

            rev = self.reversal_score(date)
            vol = self.volatility_score(date)
            if rev["reversal_score"] >= 55:
                alerts.append({"date": date, "kind": "reversal_window",
                               "title": "Reversal-prone session",
                               "note": "; ".join(d["detail"] for d in rev["drivers"][:3]),
                               "strength": min(5, int(rev["reversal_score"] // 20)),
                               "score": rev["reversal_score"]})
            if vol["volatility_score"] >= 55 and not any(
                    a["date"] == date and a["kind"] == "volatility_window" for a in alerts):
                alerts.append({"date": date, "kind": "volatility_window",
                               "title": "Volatility spike window",
                               "note": "; ".join(d["detail"] for d in vol["drivers"][:3]),
                               "strength": min(5, int(vol["volatility_score"] // 20)),
                               "score": vol["volatility_score"]})

            # stations + ingresses (raw event detection)
            for pl, (const, _, _) in {**STATION_WATCH}.items():
                _, sp = self._tropical_lon(jd, const)
                if prev_speed.get(pl, 0) * sp < 0:
                    kind = "goes retrograde" if sp < 0 else "turns direct"
                    alerts.append({"date": date, "kind": "reversal_window",
                                   "title": f"{pl} {kind}",
                                   "note": f"{pl} station - trend-exhaustion lore",
                                   "strength": 3 if pl in ("Mercury", "Venus", "Mars") else 2})
                prev_speed[pl] = sp
            for pl, (const, _, _) in INGRESS_WATCH.items():
                c = swe.MEAN_NODE if const == "mean_node" else const
                lon, _ = self._sidereal_lon(jd, c)
                if int(lon // 30) != prev_signs.get(pl, int(lon // 30)):
                    alerts.append({"date": date, "kind": "reversal_window",
                                   "title": f"{pl} enters {SIGNS[int(lon // 30)]}",
                                   "note": f"{pl} sidereal ingress - theme shift",
                                   "strength": 2})
                    prev_signs[pl] = int(lon // 30)

        alerts.sort(key=lambda a: (a["date"], -a.get("strength", 0)))
        return alerts[:40]

    # ------------------------------------------------------------------
    # AI + Astro N-day range projection (EWMA bands x astro multiplier)
    # ------------------------------------------------------------------
    def five_day_range(self, symbol: str, spot: float, closes: List[float],
                       horizon: int = 5) -> Dict:
        rets = np.diff(np.log(np.asarray(closes, dtype=float)))[-120:]
        if len(rets) < 30 or spot <= 0:
            return {}
        lam = 0.94
        weights = lam ** np.arange(len(rets))[::-1]
        weights /= weights.sum()
        ewma_var = float(np.sum(weights * rets ** 2))
        vol_d = math.sqrt(ewma_var)
        sigma_h = vol_d * math.sqrt(horizon)

        # astro multiplier from the window ahead
        today = datetime.utcnow().date()
        mult = 1.0
        for i in range(horizon):
            d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            vs = self.volatility_score(d)["volatility_score"]
            mult += (0.02 if vs >= 55 else 0.008 if vs >= 35 else 0.0)
        mult = min(1.35, mult)

        levels = {}
        for z, tag in ((1.0, "outer"), (0.5, "inner")):
            up = spot * math.exp(z * sigma_h * mult)
            dn = spot * math.exp(-z * sigma_h * mult)
            levels[tag] = {"high": round(up, 2), "low": round(dn, 2)}
        return {"symbol": symbol, "spot": round(spot, 2), "horizon_days": horizon,
                "ewma_daily_vol": round(vol_d, 5),
                "horizon_sigma": round(sigma_h, 5),
                "astro_multiplier": round(mult, 3),
                "bands": levels,
                "support": levels["outer"]["low"],
                "resistance": levels["outer"]["high"]}

    # ------------------------------------------------------------------
    # astro-technical composite (VIP-indicator analog)
    # ------------------------------------------------------------------
    def composite_signal(self, symbol: str, closes: List[float]) -> Dict:
        x = np.asarray(closes, dtype=float)
        if len(x) < 60:
            return {}

        # --- technicals -------------------------------------------------
        delta = np.diff(x)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avgg = pd_ema(gain, 14)[-1]
        avgl = pd_ema(loss, 14)[-1]
        rsi = 100.0 - 100.0 / (1.0 + (avgg / avgl if avgl > 0 else np.inf))

        ema20 = pd_ema(x, 20)[-1]
        ema50 = pd_ema(x, 50)[-1]
        trend = (ema20 - ema50) / ema50 * 100.0

        rets = np.diff(np.log(x))
        vol20 = float(np.std(rets[-20:])) * math.sqrt(252)
        vol_pct = float(np.mean(vol20 > (np.array([
            np.std(rets[max(0, i - 20):i]) * math.sqrt(252)
            for i in range(60, len(rets) + 1)]))))

        tech = 0.0
        tech += (50 - abs(rsi - 50)) * 0.0  # placeholder keep rsi informational
        tech += max(-1.0, min(1.0, (rsi - 50) / 30.0)) * 40
        tech += max(-1.0, min(1.0, trend / 2.0)) * 40
        tech -= max(0.0, (vol_pct - 0.7)) * 60  # vol regime penalty
        tech = max(-100.0, min(100.0, tech))

        # --- astro ------------------------------------------------------
        today = datetime.utcnow().date().strftime("%Y-%m-%d")
        mood = self.market_mood(today)
        astro = (mood["mood_index"] - 50.0) * 2.0  # -100..+100

        composite = 0.55 * tech + 0.45 * astro
        zone = ("Strong Buy" if composite >= 35 else
                "Buy" if composite >= 15 else
                "Neutral" if composite > -15 else
                "Sell" if composite > -35 else "Strong Sell")

        return {"symbol": symbol, "date": today,
                "technical_score": round(tech, 1),
                "astro_score": round(astro, 1),
                "composite": round(composite, 1),
                "zone": zone,
                "rsi14": round(float(rsi), 1),
                "trend_pct": round(float(trend), 2),
                "vol20_annualised": round(vol20, 4),
                "vol_percentile": round(vol_pct, 2),
                "mood": mood}


def pd_ema(arr: np.ndarray, span: int) -> np.ndarray:
    """Pandas-style EMA without importing pandas."""
    a = 2.0 / (span + 1.0)
    out = np.empty_like(arr, dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = a * arr[i] + (1 - a) * out[i - 1]
    return out
