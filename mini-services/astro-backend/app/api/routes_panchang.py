"""v1.4 Panchang + market-weather calendar (mounted under /api/v1 by app.main).

  GET /panchang?date=&lat=&lon=&tz=&place=&symbol=   five limbs, Rahu Kaal, plain-English reading
                                                     (+ the symbol's historical stats for today's
                                                     paksha and nakshatra when ``symbol`` is given)
  GET /panchang/calendar?start=&days=&...            N-day forward calendar + sky events
  GET /panchang/calendar.ics?start=&days=&...        the same as an iCalendar feed
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.panchang import calendar_ics, market_calendar, panchang

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_LOC = dict(lat=19.076, lon=72.8777, tz=5.5, place="Mumbai (NSE / BSE)")


def _day(s: Optional[str], tz: float) -> date:
    if not s:
        return datetime.now(timezone(timedelta(hours=tz))).date()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")


def _symbol_context(symbol: str, p: Dict) -> Optional[Dict]:
    """Historical returns of ``symbol`` on days sharing today's paksha / Moon nakshatra."""
    try:
        from app.api.routes_cycles import _history, _meta, _stats, _source
        name, _ = _meta(symbol)
        st = _stats(symbol, _history(symbol), name)
        if not st.get("success"):
            return None
        pk_label = "Shukla (waxing)" if p["tithi"]["paksha"] == "Shukla" else "Krishna (waning)"
        pk = next((r for r in st["paksha"]["rows"] if r["label"] == pk_label), None)
        nk = next((r for r in st["nakshatra"]["rows"] if r["label"] == p["nakshatra"]["name"]), None)
        base = st["nakshatra"]["baseline"]
        out = {"symbol": symbol, "name": name, "baseline": base, "paksha": pk, "nakshatra": nk,
               "data_source": _source()}
        if nk and nk["n"]:
            better = nk["mean_pct"] >= base["mean_pct"]
            out["plain_english"] = (
                f"On past days with the Moon in {nk['label']}, {name} closed higher "
                f"{nk['hit_pct']:.0f}% of the time (average {nk['mean_pct']:+.3f}% a day) versus "
                f"{base['hit_pct']:.0f}% on a normal day. That is {'a little better' if better else 'a little worse'} "
                f"than usual, and the statistics engine rates it '{nk['verdict']}'. Treat anything short of "
                f"'significant' as noise; past patterns do not guarantee future returns.")
        return out
    except HTTPException:
        return None
    except Exception as e:  # stats are an optional garnish — never fail the panchang
        logger.warning(f"panchang symbol context failed for {symbol}: {e}")
        return None


@router.get("/panchang")
def get_panchang(date_: Optional[str] = Query(None, alias="date"), lat: float = DEFAULT_LOC["lat"],
                 lon: float = DEFAULT_LOC["lon"], tz: float = DEFAULT_LOC["tz"],
                 place: str = DEFAULT_LOC["place"], symbol: Optional[str] = None):
    try:
        p = panchang(_day(date_, tz), lat, lon, tz, place)
        if symbol:
            p["symbol_context"] = _symbol_context(symbol, p)
        p["success"] = True
        p["disclaimer"] = "Panchang is cultural / astronomical context. Not financial advice."
        return p
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"panchang error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/panchang/calendar")
def get_calendar(start: Optional[str] = None, days: int = 30, lat: float = DEFAULT_LOC["lat"],
                 lon: float = DEFAULT_LOC["lon"], tz: float = DEFAULT_LOC["tz"],
                 place: str = DEFAULT_LOC["place"]):
    try:
        return {"success": True, **market_calendar(_day(start, tz), days, lat, lon, tz, place)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"panchang calendar error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/panchang/calendar.ics")
def get_calendar_ics(start: Optional[str] = None, days: int = 30, lat: float = DEFAULT_LOC["lat"],
                     lon: float = DEFAULT_LOC["lon"], tz: float = DEFAULT_LOC["tz"],
                     place: str = DEFAULT_LOC["place"]):
    cal = market_calendar(_day(start, tz), days, lat, lon, tz, place)
    return Response(calendar_ics(cal), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="astrotrader-panchang.ics"'})
