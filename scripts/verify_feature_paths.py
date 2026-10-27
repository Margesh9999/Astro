"""Verify the vectorised full-history feature path produces identical
columns (names + order) to the legacy prepare_planetary_features path,
and time the whole thing."""
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from app.core.ephemeris import EphemerisCalculator
from app.core.vedic import VedicCalculator
from app.core.aspects import AspectsCalculator
from app.services.correlation import CorrelationEngine
from app.services.predictor import PredictorService

eph = EphemerisCalculator("")
asc = AspectsCalculator()
corr = CorrelationEngine()

# --- legacy path for 30 recent days (tropical) ---
dates = [datetime(2026, 8, 1) + timedelta(days=i) for i in range(30)]
planetary_list = []
for dt in dates:
    jd = eph.date_to_julian(dt)
    pos = eph.calculate_all_planets(jd)
    aspects = asc.calculate_all_aspects(pos)
    for key in ("conjunction", "opposition", "trine", "square", "sextile"):
        pos[f"aspect_score_{key}"] = asc.get_aspect_score(aspects, key)
    planetary_list.append(pos)
legacy_feat, legacy_names = corr.prepare_planetary_features(planetary_list, include_aspects=False)

# --- fast path for the same 30 days, wrapped as a market_df ---
pred = PredictorService(cache_dir="/tmp/predtest")
idx = pd.DatetimeIndex(dates)
df = pd.DataFrame({"Close": np.linspace(100, 110, 30), "Returns": np.zeros(30)}, index=idx)
fast_feat, fast_ret, fast_dates, _ = pred.collect_full_history_data("__test__", vedic=False)

# collect_full_history_data caches by symbol — build directly instead:
def fast_direct(dates, vedic=False):
    import swisseph as _swe
    PLANETS = [("Sun", _swe.SUN), ("Moon", _swe.MOON), ("Mercury", _swe.MERCURY),
               ("Venus", _swe.VENUS), ("Mars", _swe.MARS), ("Jupiter", _swe.JUPITER),
               ("Saturn", _swe.SATURN), ("Uranus", _swe.URANUS), ("Neptune", _swe.NEPTUNE),
               ("Pluto", _swe.PLUTO)]
    n = len(dates)
    jds = np.array([_swe.julday(d.year, d.month, d.day, 0.0) for d in dates])
    ayanamsa = np.array([_swe.get_ayanamsa_ut(jd) for jd in jds]) if vedic else np.zeros(n)
    lons, lats, dists, speeds = {}, {}, {}, {}
    for name, pid in PLANETS:
        lon = np.empty(n); lat = np.empty(n); dist = np.empty(n); spd = np.empty(n)
        for k, jd in enumerate(jds):
            pos, _r = _swe.calc_ut(float(jd), pid)
            lon[k], lat[k], dist[k], spd[k] = pos[0], pos[1], pos[2], pos[3]
        if vedic:
            lon = (lon - ayanamsa) % 360.0
        lons[name], lats[name], dists[name], speeds[name] = lon, lat, dist, spd
    cols = {}
    for name, _p in PLANETS:
        p = name.lower(); lon = lons[name]
        sign_num = np.floor(lon / 30.0).astype(int) % 12
        cols[f"{p}_longitude"] = lon; cols[f"{p}_latitude"] = lats[name]
        cols[f"{p}_speed"] = speeds[name]; cols[f"{p}_distance"] = dists[name]
        cols[f"{p}_retrograde"] = (speeds[name] < 0).astype(float)
        for s in range(12):
            cols[f"{p}_sign_{s}"] = (sign_num == s).astype(float)
        cols[f"{p}_degree"] = lon % 30.0
        if vedic:
            nak = 360.0 / 27.0
            cols[f"{p}_nakshatra"] = np.floor(lon / nak)
            cols[f"{p}_pada"] = np.floor((lon % nak) / nak * 4.0) + 1.0
            cols[f"{p}_ayanamsa"] = ayanamsa
    SPEC = {"conjunction": (0.0, 8.0, 1.0), "opposition": (180.0, 8.0, 0.8),
            "trine": (120.0, 8.0, 0.6), "square": (90.0, 8.0, 0.7), "sextile": (60.0, 6.0, 0.4)}
    names = [nm for nm, _ in PLANETS]
    L = np.stack([lons[nm] for nm in names])
    scores = {k: np.zeros(n) for k in SPEC}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = np.abs(L[i] - L[j]) % 360.0
            diff = np.minimum(d, 360.0 - d)
            for asp, (ang, orb, w) in SPEC.items():
                dev = np.abs(diff - ang)
                scores[asp] += w * (1.0 - dev / orb) * (dev <= orb)
    for asp in SPEC:
        cols[f"aspect_score_{asp}"] = scores[asp]
    return pd.DataFrame(cols).values.astype(float), list(cols.keys())

fast_feat2, fast_names = fast_direct(dates)
print("legacy cols:", len(legacy_names), "| fast cols:", len(fast_names))
print("column order identical:", legacy_names == fast_names)
if legacy_names != fast_names:
    for a, b in zip(legacy_names, fast_names):
        if a != b:
            print("MISMATCH:", a, "vs", b); break
    else:
        print("length differs:", len(legacy_names), len(fast_names))
else:
    diff = np.abs(legacy_feat - fast_feat2)
    print("max value difference:", diff.max())

# --- aspect score spot-check for one day (legacy vs fast) ---
dt = dates[0]; jd = eph.date_to_julian(dt)
pos = eph.calculate_all_planets(jd)
asp = asc.calculate_all_aspects(pos)
legacy_scores = {k: asc.get_aspect_score(asp, k) for k in ("conjunction", "opposition", "trine", "square", "sextile")}
ff, fn = fast_direct([dt])
for i, k in enumerate(("conjunction", "opposition", "trine", "square", "sextile")):
    legacy_v = legacy_scores[k]
    fast_v = ff[0][len(fn) - 5 + i]
    print(f"aspect {k}: legacy={legacy_v:.4f} fast={fast_v:.4f} match={abs(legacy_v - fast_v) < 1e-9}")
