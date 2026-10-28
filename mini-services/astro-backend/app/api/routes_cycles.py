"""v1.3 cycles endpoints (mounted under /api/v1 by app.main).

  GET /cycles/clock                 lunar / solar / retrograde / Jupiter-Saturn cycle clock
  GET /cycles/stats/{symbol}        full-history cycle statistics (phase, paksha, nakshatra, Sun sign, retrogrades)
  GET /cycles/insight/{symbol}      layman Suri reading: today's reading, metric explanations, week plan, lunar 30d
  GET /events/study?symbol=&days=   next-N-day sky events x per-symbol event study + meaning + action
"""
import logging
import math
from datetime import datetime
from typing import Any, Dict, Tuple

from fastapi import APIRouter, HTTPException

from app.api.routes import market_service, suri_engine
from app.services import universe
from app.services.cycles_insight import (CRYPTO_SECTORS, cycle_clock, explain, lunar_calendar, todays_reading,
                                         week_plan)
from app.services.cycles_sky import SKY, warm_async
from app.services.cycles_stats import cycle_stats
from app.services.events_study import events_with_study, stock_context
from app.services.cycles_stats import PricePanel
from app.services.market_data import DEMO_DATA

logger = logging.getLogger(__name__)

router = APIRouter()

warm_async()  # build / load the sky table in the background at startup

_STATS_CACHE: Dict[Tuple[str, str], Dict] = {}


def clean(o: Any) -> Any:
    """Recursively replace NaN/Inf (illegal in JSON) and numpy scalars."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try:
            o = o.item()
        except Exception:
            pass
    if isinstance(o, float):
        return 0.0 if (math.isnan(o) or math.isinf(o)) else o
    return o


def _meta(symbol: str) -> Tuple[str, str]:
    row = universe.get(symbol)
    if row:
        return row["name"], row["sector"]
    try:
        info = market_service.get_symbol_info(symbol)
        return info.get("name") or symbol, info.get("sector") or "N/A"
    except Exception:
        return symbol, "N/A"


def _history(symbol: str):
    df = market_service.fetch_historical_data(symbol, period="max", interval="1d")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No market data for {symbol}")
    return df.dropna(subset=["Close"])


def _stats(symbol: str, df, name: str) -> Dict:
    key = (symbol, str(df.index[-1])[:10])
    if key not in _STATS_CACHE:
        if len(_STATS_CACHE) > 64:
            _STATS_CACHE.clear()
        _STATS_CACHE[key] = cycle_stats(df, symbol, name)
    return _STATS_CACHE[key]


def _source() -> str:
    return ("synthetic demo prices (ASTRO_DEMO_DATA=1) — statistics are illustrative only"
            if DEMO_DATA else "live market history (Yahoo Finance / Stooq fallback)")


@router.get("/cycles/clock")
def get_cycle_clock():
    try:
        return clean({"success": True, **cycle_clock()})
    except Exception as e:
        logger.error(f"cycle clock error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cycles/stats/{symbol}")
def get_cycle_stats(symbol: str):
    try:
        name, _sector = _meta(symbol)
        df = _history(symbol)
        st = _stats(symbol, df, name)
        if not st.get("success"):
            raise HTTPException(status_code=400, detail=st.get("error", "insufficient data"))
        return clean({**st, "data_source": _source(), "demo_data": DEMO_DATA,
                      "disclaimer": "Educational statistics — past cycles do not guarantee future returns."})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"cycle stats error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/study")
def get_events_study(symbol: str = "^GSPC", days: int = 45):
    try:
        days = max(7, min(90, days))
        name, sector = _meta(symbol)
        df = _history(symbol)
        pack = events_with_study(df, symbol, name, sector, days)
        if not pack.get("success"):
            raise HTTPException(status_code=400, detail=pack.get("error", "insufficient data"))
        return clean({**pack, "data_source": _source(), "demo_data": DEMO_DATA,
                      "disclaimer": "Educational event study — history is not a forecast. Not financial advice."})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"events study error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cycles/insight/{symbol}")
def get_cycles_insight(symbol: str):
    try:
        today = datetime.utcnow().date().strftime("%Y-%m-%d")
        name, sector = _meta(symbol)
        df = _history(symbol)
        closes = [float(c) for c in df["Close"].tail(260).tolist()]
        spot = closes[-1]
        signal = {
            "mood": suri_engine.market_mood(today),
            "reversal": suri_engine.reversal_score(today),
            "volatility": suri_engine.volatility_score(today),
            "timing_alerts": suri_engine.timing_alerts(today, days=14),
            "five_day_range": suri_engine.five_day_range(symbol, spot, closes, horizon=5),
            "composite": suri_engine.composite_signal(symbol, closes),
        }
        stats = _stats(symbol, df, name)
        events = events_with_study(df, symbol, name, sector, 45)
        ctx = stock_context(PricePanel(df.tail(400)))
        clock = cycle_clock()
        crypto = sector in CRYPTO_SECTORS or symbol.upper().endswith("-USD")
        return clean({
            "success": True, "symbol": symbol, "name": name, "sector": sector, "date": today, "spot": spot,
            **signal,
            "context": ctx,
            "reading": todays_reading(signal, clock, stats, events, name, ctx),
            "explain": explain(signal, name),
            "clock": clock,
            "week": week_plan(signal, stats, events, name, ctx, crypto),
            "lunar": lunar_calendar(stats, name, crypto),
            "overall": (stats.get("conclusions", {}) or {}).get("overall", "") if stats.get("success") else "",
            "data_source": _source(), "demo_data": DEMO_DATA,
            "inspired_by": "Mohnish Suri (AstralAlgo) concepts - educational reimplementation",
            "disclaimer": "Educational exploration only — no proven predictive value. Not financial advice.",
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"cycles insight error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router", "SKY"]
