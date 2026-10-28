"""v1.3 jataka endpoints (mounted under /api/v1 by app.main)."""
import logging
import math
import threading
import time
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException

from app.services.jataka import JatakaEngine
from app.services.jataka_geo import PLACES
from app.services.jataka_stock import stock_kundli
from app.services import market_data as _md

logger = logging.getLogger(__name__)
router = APIRouter()

_engine = JatakaEngine()
_market = _md.MarketDataService()
_CACHE: Dict[str, tuple] = {}
_LOCK = threading.Lock()
_TTL = 900.0


def _clean(o):
    """Recursively replace NaN/Inf with None (FastAPI JSON rejects them)."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def birth_kwargs(name: str = "", date: str = "", time: str = "", place: str = "",
                 lat: Optional[float] = None, lon: Optional[float] = None, tz: Optional[float] = None,
                 tz_name: str = "", node: str = "mean", ayanamsa: str = "lahiri") -> Dict:
    return {"name": name, "date": date, "time": time, "place": place, "lat": lat, "lon": lon,
            "tz": tz, "tz_name": tz_name, "node": node, "ayanamsa": ayanamsa}


@router.get("/jataka/gazetteer")
async def jataka_gazetteer():
    """Full list of built-in birth places (name, lat, lon, IANA tz)."""
    return {"success": True, "count": len(PLACES),
            "places": [{k: p[k] for k in ("name", "lat", "lon", "tz_name", "country")} for p in PLACES]}


@router.get("/jataka/stock-correlation")
def jataka_stock_correlation(symbol: str = "^GSPC", name: str = "", date: str = "", time: str = "",
                             place: str = "", lat: Optional[float] = None, lon: Optional[float] = None,
                             tz: Optional[float] = None, tz_name: str = "", node: str = "mean",
                             ayanamsa: str = "lahiri"):
    """Stock × Kundli: dasha-period returns, transit-to-natal edges, synastry and a verdict.

    Sync handler → FastAPI runs it in a worker thread (the first call per symbol does a
    full-history ephemeris pass, ~1-4 s; later calls are cached)."""
    kw = birth_kwargs(name, date, time, place, lat, lon, tz, tz_name, node, ayanamsa)
    key = f"{symbol}|{sorted(kw.items())}"
    now = time_mod()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    try:
        with _LOCK:  # swisseph sidereal mode is process-global → serialise chart maths
            chart = _engine.compute_chart(**kw)
        df = _market.fetch_historical_data(symbol, period="max", interval="1d")
        if df is None or df.empty or "Close" not in df:
            return {"success": False, "symbol": symbol,
                    "error": f"No price history available for {symbol} — market data unavailable, nothing fabricated."}
        info = _market.get_symbol_info(symbol)
        sname = info.get("name", symbol) if isinstance(info, dict) else symbol
        with _LOCK:
            out = stock_kundli(df["Close"].astype(float), symbol, sname, chart, demo=_md.DEMO_DATA)
        out = _clean(out)
        with _LOCK:
            _CACHE[key] = (now, out)
            if len(_CACHE) > 64:
                _CACHE.pop(next(iter(_CACHE)))
        return out
    except Exception as e:  # pragma: no cover - surfaced to the UI
        logger.exception("stock-correlation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def time_mod() -> float:
    return time.time()
