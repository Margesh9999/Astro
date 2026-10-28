"""
v1.3 feature engineering for the Model Lab.

Builds ONE row per trading session over the stock's ENTIRE available history
(period="max") with:

* planetary features for the session date (sidereal/Lahiri by default):
  longitude as sin/cos, sign, speed, retrograde flag for 11 bodies (incl. Rahu
  mean node), Moon nakshatra/pada/lord, tithi, paksha, lunar phase, aspect
  scores, Jupiter-Saturn & Mars-Saturn separations, retrograde count, eclipse
  season, weekday/month;
* technical features computed ONLY from information up to the PREVIOUS close
  (lagged returns, momentum, realised volatility, RSI, distance from moving
  averages, drawdown, range, volume z-score) — no look-ahead.

Targets: y1 = the session's simple return, y5/y20 = log return over the next
5/20 sessions starting at that session. The frame is extended by one future
business day so the last row is "tomorrow" (features known, target unknown).

Everything is vectorised; the frame is disk-cached per (symbol, vedic, last
date) so repeat runs are instant.
"""
from __future__ import annotations

import logging
import os
import pickle
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import swisseph as swe

logger = logging.getLogger(__name__)

BODIES: List[Tuple[str, int]] = [
    ("sun", swe.SUN), ("moon", swe.MOON), ("mercury", swe.MERCURY), ("venus", swe.VENUS),
    ("mars", swe.MARS), ("jupiter", swe.JUPITER), ("saturn", swe.SATURN),
    ("rahu", swe.MEAN_NODE), ("uranus", swe.URANUS), ("neptune", swe.NEPTUNE), ("pluto", swe.PLUTO),
]
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
ASPECTS = {"conjunction": (0.0, 8.0, 1.0), "opposition": (180.0, 8.0, 0.8),
           "trine": (120.0, 8.0, 0.6), "square": (90.0, 8.0, 0.7), "sextile": (60.0, 6.0, 0.4)}
FEATURE_VERSION = 3


# ---------------------------------------------------------------------------
# Plain-English meaning of every feature (used by the insights layer)
# ---------------------------------------------------------------------------
_PLANET_EN = {"sun": "the Sun", "moon": "the Moon", "mercury": "Mercury", "venus": "Venus",
              "mars": "Mars", "jupiter": "Jupiter", "saturn": "Saturn", "rahu": "Rahu (lunar node)",
              "uranus": "Uranus", "neptune": "Neptune", "pluto": "Pluto"}
_STATIC_MEANING: Dict[str, str] = {
    "ret_lag1": "yesterday's return — tests short-term momentum or mean-reversion",
    "ret_lag2": "the return two sessions ago",
    "ret_lag3": "the return three sessions ago",
    "ret_lag5": "the return five sessions ago",
    "mom_5": "the past week's price change (short momentum)",
    "mom_20": "the past month's price change (1-month momentum)",
    "mom_60": "the past quarter's price change (3-month momentum)",
    "mom_250": "the past year's price change (12-month trend)",
    "vol_20": "how jumpy the stock was over the last month (realised volatility)",
    "vol_60": "realised volatility over the last quarter",
    "vol_ratio": "whether volatility is rising (>1) or calming (<1) versus its quarterly norm",
    "rsi_14": "RSI(14) — overbought above 70, oversold below 30",
    "dist_sma50": "how far price sits above/below its 50-day average",
    "dist_sma200": "how far price sits above/below its 200-day average (long trend)",
    "drawdown_252": "how far price is below its 1-year high",
    "range_lag1": "yesterday's high-low range as a share of price (intraday stress)",
    "volume_z20": "whether yesterday's volume was unusually heavy versus the last month",
    "moon_phase_sin": "the lunar phase (waxing vs waning half of the cycle)",
    "moon_phase_cos": "the lunar phase (new moon = +1, full moon = −1)",
    "tithi": "the tithi (lunar day 1–30 of the Hindu calendar)",
    "shukla_paksha": "waxing-Moon fortnight (Shukla) versus waning (Krishna)",
    "days_from_full_moon": "how many days the session is from the nearest full moon",
    "moon_nakshatra": "the Moon's nakshatra (one of 27 lunar mansions)",
    "moon_pada": "the quarter (pada) of the Moon's nakshatra",
    "moon_nak_lord": "the Vimshottari lord ruling the Moon's nakshatra",
    "sun_nakshatra": "the Sun's nakshatra",
    "aspect_score_conjunction": "how many planets are tightly conjunct (bunched together)",
    "aspect_score_opposition": "strength of planetary oppositions (tension axis)",
    "aspect_score_trine": "strength of trines (traditionally 'easy' aspects)",
    "aspect_score_square": "strength of squares (traditionally 'hard' aspects)",
    "aspect_score_sextile": "strength of sextiles (mild supportive aspects)",
    "jup_sat_sep": "the Jupiter–Saturn separation (the ~20-year business-cycle pair)",
    "mars_sat_sep": "the Mars–Saturn separation (a classic 'stress' pairing)",
    "n_retro": "how many of Mercury..Saturn are retrograde at once",
    "eclipse_season": "eclipse season — the Sun within 18° of the Rahu/Ketu axis",
    "weekday": "the day of the week (also its Vedic weekday lord)",
    "month": "the calendar month (seasonality)",
}


def feature_meaning(name: str) -> str:
    if name in _STATIC_MEANING:
        return _STATIC_MEANING[name]
    for p, en in _PLANET_EN.items():
        if name.startswith(p + "_"):
            rest = name[len(p) + 1:]
            return {
                "lon_sin": f"where {en} sits in the zodiac (east–west component)",
                "lon_cos": f"where {en} sits in the zodiac (north–south component)",
                "sign": f"the rashi (zodiac sign) {en} occupies",
                "speed": f"how fast {en} is moving across the sky (slow = stationing)",
                "retro": f"whether {en} is retrograde",
            }.get(rest, f"{en}: {rest.replace('_', ' ')}")
    return name.replace("_", " ")


def feature_group(name: str) -> str:
    tech = ("ret_", "mom_", "vol_", "rsi", "dist_", "drawdown", "range_", "volume")
    if name.startswith(tech):
        return "technical"
    if name in ("weekday", "month"):
        return "calendar"
    return "astro"


# ---------------------------------------------------------------------------
def _ephemeris(dates: pd.DatetimeIndex, vedic: bool) -> Dict[str, np.ndarray]:
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    if vedic:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL
    jds = (dates.values.astype("datetime64[s]").astype(np.int64) / 86400.0) + 2440587.5 + 0.5  # 12:00 UT
    out: Dict[str, np.ndarray] = {}
    n = len(jds)
    for name, pid in BODIES:
        lon = np.empty(n)
        spd = np.empty(n)
        for k in range(n):
            pos, _ = swe.calc_ut(float(jds[k]), pid, flags)
            lon[k] = pos[0]
            spd[k] = pos[3]
        out[f"{name}_lon"] = lon % 360.0
        out[f"{name}_spd"] = spd
    return out


def _sep(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = np.abs(a - b) % 360.0
    return np.minimum(d, 360.0 - d)


def build_astro_frame(dates: pd.DatetimeIndex, vedic: bool = True) -> pd.DataFrame:
    eph = _ephemeris(dates, vedic)
    cols: Dict[str, np.ndarray] = {}
    for name, _ in BODIES:
        lon = eph[f"{name}_lon"]
        rad = np.deg2rad(lon)
        cols[f"{name}_lon_sin"] = np.sin(rad)
        cols[f"{name}_lon_cos"] = np.cos(rad)
        cols[f"{name}_sign"] = np.floor(lon / 30.0) % 12
        if name not in ("sun", "moon", "rahu"):
            cols[f"{name}_speed"] = eph[f"{name}_spd"]
            cols[f"{name}_retro"] = (eph[f"{name}_spd"] < 0).astype(float)
        elif name == "moon":
            cols["moon_speed"] = eph["moon_spd"]
    sun, moon, rahu = eph["sun_lon"], eph["moon_lon"], eph["rahu_lon"]
    elong = (moon - sun) % 360.0
    cols["moon_phase_sin"] = np.sin(np.deg2rad(elong))
    cols["moon_phase_cos"] = np.cos(np.deg2rad(elong))
    cols["tithi"] = np.floor(elong / 12.0) + 1.0
    cols["shukla_paksha"] = (elong < 180.0).astype(float)
    cols["days_from_full_moon"] = np.abs(elong - 180.0) / 12.19
    nak_span = 360.0 / 27.0
    mnak = np.floor(moon / nak_span) % 27
    cols["moon_nakshatra"] = mnak
    cols["moon_pada"] = np.floor((moon % nak_span) / nak_span * 4.0) + 1.0
    cols["moon_nak_lord"] = mnak % 9
    cols["sun_nakshatra"] = np.floor(sun / nak_span) % 27
    # aspect scores over the 10 physical planets (node excluded)
    names = [n for n, _ in BODIES if n != "rahu"]
    L = [eph[f"{n}_lon"] for n in names]
    scores = {k: np.zeros(len(dates)) for k in ASPECTS}
    for i in range(len(L)):
        for j in range(i + 1, len(L)):
            diff = _sep(L[i], L[j])
            for asp, (ang, orb, w) in ASPECTS.items():
                dev = np.abs(diff - ang)
                scores[asp] += w * np.clip(1.0 - dev / orb, 0.0, None)
    for asp in ASPECTS:
        cols[f"aspect_score_{asp}"] = scores[asp]
    cols["jup_sat_sep"] = _sep(eph["jupiter_lon"], eph["saturn_lon"])
    cols["mars_sat_sep"] = _sep(eph["mars_lon"], eph["saturn_lon"])
    cols["n_retro"] = sum((eph[f"{p}_spd"] < 0).astype(float) for p in ("mercury", "venus", "mars", "jupiter", "saturn"))
    node_dist = np.minimum(_sep(sun, rahu), _sep(sun, (rahu + 180.0) % 360.0))
    cols["eclipse_season"] = (node_dist < 18.0).astype(float)
    cols["weekday"] = dates.dayofweek.values.astype(float)
    cols["month"] = dates.month.values.astype(float)
    return pd.DataFrame(cols, index=dates)


def build_technical_frame(px: pd.DataFrame) -> pd.DataFrame:
    """Technical features at row t use information up to close t-1 only."""
    close = px["Close"].astype(float)
    r = close.pct_change()
    lr = np.log(close).diff()
    f = pd.DataFrame(index=px.index)
    f["ret_lag1"] = r
    f["ret_lag2"] = r.shift(1)
    f["ret_lag3"] = r.shift(2)
    f["ret_lag5"] = r.shift(4)
    for w in (5, 20, 60, 250):
        f[f"mom_{w}"] = close / close.shift(w) - 1.0
    f["vol_20"] = lr.rolling(20, min_periods=10).std() * np.sqrt(252)
    f["vol_60"] = lr.rolling(60, min_periods=30).std() * np.sqrt(252)
    f["vol_ratio"] = f["vol_20"] / f["vol_60"]
    up = r.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-r.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi_14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    f["dist_sma50"] = close / close.rolling(50, min_periods=25).mean() - 1.0
    f["dist_sma200"] = close / close.rolling(200, min_periods=100).mean() - 1.0
    f["drawdown_252"] = close / close.rolling(252, min_periods=20).max() - 1.0
    if {"High", "Low"}.issubset(px.columns):
        f["range_lag1"] = (px["High"] - px["Low"]) / close
    if "Volume" in px.columns and float(px["Volume"].fillna(0).sum()) > 0:
        v = px["Volume"].astype(float).replace(0, np.nan)
        f["volume_z20"] = (v - v.rolling(20, min_periods=10).mean()) / v.rolling(20, min_periods=10).std()
    # shift everything by one session → only yesterday's information is used
    return f.shift(1)


def build_dataset(px: pd.DataFrame, vedic: bool = True) -> pd.DataFrame:
    """Full feature frame + targets, extended by one future business day."""
    px = px[~px.index.duplicated(keep="last")].sort_index()
    idx = pd.DatetimeIndex(pd.to_datetime(px.index)).tz_localize(None).normalize()
    px = px.copy()
    px.index = idx
    nxt = idx[-1] + pd.offsets.BDay(1)
    ext = px.reindex(idx.append(pd.DatetimeIndex([nxt])))
    tech = build_technical_frame(ext)
    astro = build_astro_frame(ext.index, vedic)
    df = pd.concat([astro, tech], axis=1)
    close = ext["Close"].astype(float)
    df["y1"] = close.pct_change()
    logc = np.log(close)
    for h in (5, 20):
        df[f"y{h}"] = logc.shift(-(h - 1)) - logc.shift(1)
    df["close"] = close
    df = df.replace([np.inf, -np.inf], np.nan)
    feats = [c for c in df.columns if c not in ("y1", "y5", "y20", "close")]
    df[feats] = df[feats].ffill().fillna(0.0)
    return df.iloc[1:]  # first row has no return


def target_columns() -> List[str]:
    return ["y1", "y5", "y20", "close"]


def feature_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if c not in target_columns()]


def load_dataset(market_service, symbol: str, vedic: bool = True) -> Tuple[pd.DataFrame, str]:
    """period="max" history → cached feature frame. Returns (frame, last_date)."""
    px = market_service.fetch_historical_data(symbol, period="max", interval="1d")
    if px is None or px.empty:
        return pd.DataFrame(), ""
    stamp = str(pd.Timestamp(px.index.max()).date())
    cache_dir = getattr(market_service, "cache_dir", "./data")
    safe = symbol.replace("^", "idx_").replace(".", "_").replace("=", "_").replace("/", "_")
    path = os.path.join(cache_dir, f"mlfeat_v{FEATURE_VERSION}_{safe}_{int(vedic)}.pkl")
    if os.path.exists(path):
        try:
            with open(path, "rb") as fh:
                blob = pickle.load(fh)
            if blob.get("stamp") == stamp and blob.get("rows") == len(px):
                return blob["df"], stamp
        except Exception:
            pass
    df = build_dataset(px, vedic)
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump({"stamp": stamp, "rows": len(px), "df": df}, fh)
    except Exception as exc:
        logger.warning(f"feature cache write failed: {exc}")
    return df, stamp
