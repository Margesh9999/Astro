"""
Shared helpers for the v1.3 Quant Desk services: JSON sanitising, a small
per-symbol TTL cache, OHLCV normalisation and plain-English "insight"
triplets (what it shows / what it means / what to do).
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
import pandas as pd

CACHE_TTL = 15 * 60

_cache: Dict[Tuple[str, str], Tuple[float, Any]] = {}
_locks: Dict[Tuple[str, str], threading.Lock] = {}
_locks_guard = threading.Lock()


def cached(kind: str, symbol: str, fn: Callable[[], Any], ttl: int = CACHE_TTL) -> Any:
    """Compute-once-per-TTL cache keyed by (kind, symbol). Concurrent callers
    for the same key wait for the first computation instead of duplicating it."""
    key = (kind, symbol)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        val = fn()
        _cache[key] = (time.time(), val)
        return val


def clear_cache() -> None:
    _cache.clear()


def clean(obj: Any, nd: int = 6) -> Any:
    """Recursively convert numpy/pandas scalars to Python and NaN/Inf to None."""
    if isinstance(obj, dict):
        return {str(k): clean(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v, nd) for v in obj]
    if isinstance(obj, np.ndarray):
        return [clean(v, nd) for v in obj.tolist()]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, nd)
    if isinstance(obj, (pd.Timestamp,)):
        return str(obj.date())
    return obj


def r(x: Any, nd: int = 2) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, nd)


def naive(df: pd.DataFrame) -> pd.DataFrame:
    """Drop tz info, keep OHLCV, forward-fill missing OHLC from Close."""
    d = df.copy()
    idx = pd.DatetimeIndex(d.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    d.index = idx.normalize()
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d[d["Close"].notna() & (d["Close"] > 0)]
    for c in ("Open", "High", "Low"):
        if c not in d.columns:
            d[c] = d["Close"]
        d[c] = d[c].where(d[c] > 0, d["Close"])
    if "Volume" not in d.columns:
        d["Volume"] = 0.0
    d["Volume"] = d["Volume"].fillna(0.0)
    d["High"] = d[["High", "Close", "Open"]].max(axis=1)
    d["Low"] = d[["Low", "Close", "Open"]].min(axis=1)
    return d[["Open", "High", "Low", "Close", "Volume"]].astype(float)


def insight(shows: str, means: str, action: str) -> Dict[str, str]:
    """The house plain-English triplet carried by every chart."""
    return {"shows": shows, "means": means, "action": action}


def downsample(n: int, max_points: int) -> np.ndarray:
    """Indices to keep so a series of length n has at most max_points (always keeps last)."""
    if n <= max_points:
        return np.arange(n)
    step = int(math.ceil(n / max_points))
    idx = np.arange(n - 1, -1, -step)[::-1]
    return idx


def fmt_pct(x: float, nd: int = 1, sign: bool = True) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "n/a"
    return f"{x:+.{nd}f}%" if sign else f"{x:.{nd}f}%"


BENCH_NAMES: Dict[str, str] = {
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq Comp.", "^DJI": "Dow Jones", "^FTSE": "FTSE 100",
    "^NSEI": "Nifty 50", "^BSESN": "Sensex", "GC=F": "Gold", "CL=F": "Crude oil",
    "^VIX": "VIX", "^TNX": "US 10y yield", "GBPUSD=X": "GBP/USD",
}


def market_benchmark(symbol: str, market: Optional[str]) -> str:
    """Pick the natural home-market benchmark for beta (never the symbol itself)."""
    pref = {"India": "^NSEI", "UK": "^FTSE"}.get(market or "", "^GSPC")
    if pref == symbol:
        pref = "^GSPC" if symbol != "^GSPC" else "^DJI"
    return pref
