"""
Cycles sky table (v1.3)
=======================
One daily (noon-UT) table of sidereal (Lahiri) longitudes and speeds for the
nine Vedic grahas from 1925 to two years ahead, computed once with Swiss
Ephemeris (Moshier) and cached on disk + in memory. Everything in the cycles
area — historical cycle statistics, event studies, the cycle clock — reads
from this table, so the expensive ephemeris work is paid exactly once.

Also detects every classical event in the table (lunations, eclipses,
stations, sidereal ingresses, aspects, combustion) and caches the list.
Educational only.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import swisseph as swe

from app.core.config import settings

logger = logging.getLogger(__name__)

FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED
START = date(1925, 1, 1)

BODIES: Dict[str, int] = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE,
}
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
         "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
RASHI = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula",
         "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena"]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
              "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
              "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
              "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
              "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"] * 3
PHASES8 = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
           "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"]
TITHI_NAMES = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
               "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
               "Trayodashi", "Chaturdashi"]
RETRO_PLANETS = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
# classical combustion orbs (degrees from the Sun)
COMBUST_ORB = {"Mercury": 14.0, "Venus": 10.0, "Mars": 17.0, "Jupiter": 11.0, "Saturn": 15.0}
SLOW = {"Jupiter", "Saturn", "Rahu"}
ASPECTS = {0: "conjunction", 90: "square", 120: "trine", 180: "opposition", 240: "trine", 270: "square"}
ASPECT_PLANETS = ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu"]


def tithi_name(t: int) -> str:
    """t in 1..30 -> 'Shukla Saptami' / 'Purnima' / 'Amavasya'."""
    if t == 15:
        return "Purnima (Full Moon)"
    if t == 30:
        return "Amavasya (New Moon)"
    paksha = "Shukla" if t < 15 else "Krishna"
    return f"{paksha} {TITHI_NAMES[(t - 1) % 15]}"


class SkyTable:
    """Daily ephemeris table + derived cycle states + detected events."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or settings.ASTRO_CACHE_DIR
        self._lock = threading.Lock()
        self._ready = False
        self._events: Optional[List[Dict]] = None
        self._js_cache: Optional[Dict] = None

    # ------------------------------------------------------------------
    # build / load
    # ------------------------------------------------------------------
    @property
    def end(self) -> date:
        return date(datetime.utcnow().year + 2, 1, 1)

    def _path(self) -> str:
        return os.path.join(self.cache_dir, f"sky_table_v2_{START.isoformat()}_{self.end.isoformat()}.npz")

    def ensure(self) -> "SkyTable":
        if self._ready:
            return self
        with self._lock:
            if self._ready:
                return self
            path = self._path()
            arrs = None
            if os.path.exists(path):
                try:
                    z = np.load(path)
                    arrs = {k: z[k] for k in z.files}
                except Exception as exc:  # corrupt cache -> rebuild
                    logger.warning(f"sky table cache unreadable ({exc}); rebuilding")
            if arrs is None:
                arrs = self._compute()
                try:
                    os.makedirs(self.cache_dir, exist_ok=True)
                    np.savez_compressed(path, **arrs)
                except Exception as exc:
                    logger.warning(f"could not persist sky table: {exc}")
            self._load(arrs)
            self._ready = True
        return self

    def _compute(self) -> Dict[str, np.ndarray]:
        t0 = datetime.utcnow()
        jd0 = swe.julday(START.year, START.month, START.day, 12.0)
        n = (self.end - START).days
        jd = jd0 + np.arange(n, dtype=float)
        out: Dict[str, np.ndarray] = {"jd": jd}
        ayan = np.empty(n)
        for i, j in enumerate(jd):
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)  # process-global: re-pin (other modules switch it)
            ayan[i] = swe.get_ayanamsa_ut(j)
        out["ayan"] = ayan
        for name, pid in BODIES.items():
            lon = np.empty(n)
            spd = np.empty(n)
            for i, j in enumerate(jd):
                pos, _ = swe.calc_ut(j, pid, FLAGS)
                lon[i] = pos[0]
                spd[i] = pos[3]
            out[f"lon_{name}"] = (lon - ayan) % 360.0
            out[f"spd_{name}"] = spd
        logger.info(f"sky table computed: {n} days in {(datetime.utcnow() - t0).total_seconds():.1f}s")
        return out

    def _load(self, a: Dict[str, np.ndarray]) -> None:
        self.jd = a["jd"]
        self.n = len(self.jd)
        self.dates = np.datetime64(START.isoformat(), "D") + np.arange(self.n)
        self.lon = {k: a[f"lon_{k}"] for k in BODIES}
        self.spd = {k: a[f"spd_{k}"] for k in BODIES}
        el = (self.lon["Moon"] - self.lon["Sun"]) % 360.0
        self.elong = el
        self.tithi = (np.floor(el / 12.0).astype(int) + 1).clip(1, 30)
        self.paksha = (el >= 180.0).astype(int)  # 0 Shukla (waxing), 1 Krishna (waning)
        self.phase8 = (np.floor(((el + 22.5) % 360.0) / 45.0).astype(int)) % 8
        self.nakshatra = (np.floor(self.lon["Moon"] / (360.0 / 27.0)).astype(int)) % 27
        self.sun_sign = (np.floor(self.lon["Sun"] / 30.0).astype(int)) % 12
        self.retro = {p: self.spd[p] < 0 for p in RETRO_PLANETS}

    # ------------------------------------------------------------------
    # index helpers
    # ------------------------------------------------------------------
    def idx(self, d) -> int:
        """Row index of a calendar date (date / 'YYYY-MM-DD' / datetime64)."""
        if isinstance(d, str):
            d = date.fromisoformat(d[:10])
        if isinstance(d, datetime):
            d = d.date()
        if isinstance(d, date):
            return (d - START).days
        return int((np.datetime64(d, "D") - self.dates[0]).astype(int))

    def date_of(self, i: int) -> str:
        return str(self.dates[int(i)])

    def today_idx(self) -> int:
        return self.idx(datetime.utcnow().date())

    def next_where(self, mask: np.ndarray, start: int) -> Optional[int]:
        hits = np.flatnonzero(mask[start:])
        return int(start + hits[0]) if hits.size else None

    # ------------------------------------------------------------------
    # event detection (whole table, cached)
    # ------------------------------------------------------------------
    def events(self) -> List[Dict]:
        self.ensure()
        if self._events is not None:
            return self._events
        with self._lock:
            if self._events is None:
                t0 = datetime.utcnow()
                ev: List[Dict] = []
                ev += self._lunations()
                ev += self._eclipses()
                ev += self._stations()
                ev += self._ingresses()
                ev += self._aspects()
                ev += self._combustion()
                ev.sort(key=lambda e: (e["i"], e["key"]))
                self._events = ev
                logger.info(f"sky events detected: {len(ev)} in {(datetime.utcnow() - t0).total_seconds():.1f}s")
        return self._events

    def _mk(self, i: int, key: str, family: str, title: str, planets: List[str], importance: str,
            **extra) -> Dict:
        return {"i": int(i), "date": self.date_of(i), "key": key, "family": family, "title": title,
                "planets": planets, "importance": importance, **extra}

    @staticmethod
    def _crossings(series: np.ndarray, target: float) -> np.ndarray:
        """Indices i where an angle series crosses `target` between day i-1 and i
        (series in 0..360, minimal-step unwrapped)."""
        un = np.unwrap(np.radians(series)) * 180.0 / np.pi
        rel = un - target
        k_prev = np.floor(rel[:-1] / 360.0)
        k_now = np.floor(rel[1:] / 360.0)
        return np.flatnonzero(k_prev != k_now) + 1

    def _lunations(self) -> List[Dict]:
        out = []
        spec = [(0.0, "new", "New Moon (Amavasya)", "High"), (180.0, "full", "Full Moon (Purnima)", "High"),
                (90.0, "first_quarter", "First Quarter Moon", "Low"),
                (270.0, "last_quarter", "Last Quarter Moon", "Low")]
        for ang, k, title, imp in spec:
            for i in self._crossings(self.elong, ang):
                nk = NAKSHATRAS[self.nakshatra[i]]
                out.append(self._mk(i, f"lunation:{k}", "lunation", f"{title} in {nk}", ["Sun", "Moon"], imp))
        return out

    def _eclipses(self) -> List[Dict]:
        out = []
        jd_end = self.jd[-1]
        jd = self.jd[0]
        while jd < jd_end:
            try:
                fl, tret = swe.sol_eclipse_when_glob(jd, swe.FLG_MOSEPH)
            except Exception:
                break
            t = tret[0]
            if t >= jd_end:
                break
            kind = ("total" if fl & swe.ECL_TOTAL else "annular" if fl & swe.ECL_ANNULAR else
                    "hybrid" if fl & swe.ECL_ANNULAR_TOTAL else "partial")
            i = int(round(t - self.jd[0]))
            out.append(self._mk(i, "eclipse:solar", "eclipse", f"Solar eclipse ({kind}) — Surya grahan",
                                ["Sun", "Moon", "Rahu"], "High", subtype=kind))
            jd = t + 20
        jd = self.jd[0]
        while jd < jd_end:
            try:
                fl, tret = swe.lun_eclipse_when(jd, swe.FLG_MOSEPH)
            except Exception:
                break
            t = tret[0]
            if t >= jd_end:
                break
            i = int(round(t - self.jd[0]))
            if fl & swe.ECL_PENUMBRAL and not (fl & (swe.ECL_TOTAL | swe.ECL_PARTIAL)):
                out.append(self._mk(i, "eclipse:lunar_penumbral", "eclipse",
                                    "Penumbral lunar eclipse (faint)", ["Sun", "Moon", "Rahu"], "Medium",
                                    subtype="penumbral"))
            else:
                kind = "total" if fl & swe.ECL_TOTAL else "partial"
                out.append(self._mk(i, "eclipse:lunar", "eclipse", f"Lunar eclipse ({kind}) — Chandra grahan",
                                    ["Sun", "Moon", "Rahu"], "High", subtype=kind))
            jd = t + 20
        return out

    def _stations(self) -> List[Dict]:
        out = []
        for p in RETRO_PLANETS:
            s = self.spd[p]
            flips = np.flatnonzero(np.sign(s[:-1]) != np.sign(s[1:])) + 1
            for i in flips:
                retro = s[i] < 0
                kind = "retro" if retro else "direct"
                out.append(self._mk(i, f"station:{p}:{kind}", "station",
                                    f"{p} turns {'retrograde' if retro else 'direct'} in {SIGNS[int(self.lon[p][i] // 30)]}",
                                    [p], "High" if p in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn") else "Medium",
                                    planet=p, direction=kind))
        return out

    def _ingresses(self) -> List[Dict]:
        out = []
        for p in ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu"]:
            sg = (np.floor(self.lon[p] / 30.0).astype(int)) % 12
            ch = np.flatnonzero(sg[:-1] != sg[1:]) + 1
            last_i = -999
            for i in ch:
                # Rahu/retro planets can flicker across a boundary: skip re-crossings within 3 days
                if i - last_i <= 3:
                    last_i = i
                    continue
                last_i = i
                into = SIGNS[sg[i]]
                imp = "High" if p in SLOW else "Medium"
                title = (f"Sun enters {into} — {RASHI[sg[i]]} Sankranti" if p == "Sun"
                         else f"{p} enters {into}" + (" (Ketu enters " + SIGNS[(sg[i] + 6) % 12] + ")" if p == "Rahu" else ""))
                out.append(self._mk(i, f"ingress:{p}:{into}", "ingress", title, [p], imp, planet=p, into=into))
        return out

    def _aspects(self) -> List[Dict]:
        out = []
        names = ASPECT_PLANETS
        for a_i, p1 in enumerate(names):
            for p2 in names[a_i + 1:]:
                if {p1, p2} <= {"Sun", "Mercury", "Venus"} and not (p1 == "Mercury" and p2 == "Venus"):
                    # Sun-Mercury / Sun-Venus conjunctions are handled as combustion
                    continue
                sep = (self.lon[p1] - self.lon[p2]) % 360.0
                for ang, label in ASPECTS.items():
                    if p2 == "Rahu" and label not in ("conjunction", "opposition"):
                        continue
                    idxs = self._crossings(sep, float(ang))
                    last = -999
                    for i in idxs:
                        if i - last <= 2:  # flicker guard
                            last = i
                            continue
                        last = i
                        if p2 == "Rahu" and label == "opposition":
                            title, key = f"{p1} conjunct Ketu", f"aspect:{p1}-Ketu:conjunction"
                        else:
                            title, key = f"{p1} {label} {p2}", f"aspect:{p1}-{p2}:{label}"
                        slow_n = len({p1, p2} & SLOW | ({p1, p2} & {"Mars"}))
                        if label in ("conjunction", "opposition", "square") and slow_n >= 2:
                            imp = "High"
                        elif {p1, p2} & (SLOW | {"Mars"}):
                            imp = "Medium"
                        else:
                            imp = "Low"
                        out.append(self._mk(i, key, "aspect", title, [p1, p2], imp, aspect=label))
        return out

    def _combustion(self) -> List[Dict]:
        out = []
        for p, orb in COMBUST_ORB.items():
            d = np.abs((self.lon[p] - self.lon["Sun"] + 180.0) % 360.0 - 180.0)
            inside = d <= orb
            starts = np.flatnonzero(~inside[:-1] & inside[1:]) + 1
            for i in starts:
                ends = np.flatnonzero(~inside[i:])
                dur = int(ends[0]) if ends.size else 0
                out.append(self._mk(i, f"combust:{p}", "combustion",
                                    f"{p} becomes combust (within {orb:.0f}° of the Sun)", [p, "Sun"],
                                    "Medium" if p in ("Mercury", "Venus") else "Low", planet=p, days=dur))
        return out

    # ------------------------------------------------------------------
    # Jupiter-Saturn long cycle (coarse scan, beyond the daily table)
    # ------------------------------------------------------------------
    def jupiter_saturn(self) -> Dict:
        if self._js_cache and self._js_cache.get("day") == datetime.utcnow().date().isoformat():
            return self._js_cache
        today = datetime.utcnow().date()
        jd0 = swe.julday(today.year, today.month, today.day, 12.0)
        step = 2.0
        span = np.arange(-25 * 365.25, 25 * 365.25, step)
        sep = np.array([(swe.calc_ut(jd0 + s, swe.JUPITER, FLAGS)[0][0] -
                         swe.calc_ut(jd0 + s, swe.SATURN, FLAGS)[0][0]) % 360.0 for s in span])
        un = np.unwrap(np.radians(sep)) * 180.0 / np.pi
        now_i = int(np.argmin(np.abs(span)))
        res = {"day": today.isoformat(), "separation": float(sep[now_i])}
        for tgt, name in ((0.0, "conjunction"), (180.0, "opposition"), (90.0, "square"), (270.0, "square")):
            k = np.floor((un - tgt) / 360.0)
            cross = np.flatnonzero(k[:-1] != k[1:]) + 1
            fut = cross[cross > now_i]
            past = cross[cross <= now_i]
            if fut.size:
                d = today + timedelta(days=float(span[fut[0]]))
                prev = res.get(f"next_{name}")
                if not prev or d.isoformat() < prev:
                    res[f"next_{name}"] = d.isoformat()
            if past.size:
                d = today + timedelta(days=float(span[past[-1]]))
                prev = res.get(f"last_{name}")
                if not prev or d.isoformat() > prev:
                    res[f"last_{name}"] = d.isoformat()
        self._js_cache = res
        return res


SKY = SkyTable()


def warm_async() -> None:
    """Build/load the table + events in a background thread at startup."""
    def _run():
        try:
            SKY.ensure()
            SKY.events()
        except Exception as exc:  # pragma: no cover - logged only
            logger.error(f"sky warm-up failed: {exc}")
    threading.Thread(target=_run, daemon=True, name="sky-warm").start()
