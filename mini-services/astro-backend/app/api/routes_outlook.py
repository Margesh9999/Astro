"""v1.6 Market Outlook endpoint (mounted under /api/v1 by app.main).

  GET /outlook?date=&capital=&name=&date_of_birth=&time=&place=&lat=&lon=&tz=&tz_name=
      Astrology-based sector forecast for the week / month / year ahead, each call back-tested on
      the sector's real prices, plus an income plan (weekly / monthly / yearly fund buckets) sized
      by the jataka's strategy fits when birth details are given.
"""
import logging
import threading
import time
from datetime import date
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.routes_jataka import _LOCK as _CHART_LOCK, _clean, _engine, _market, birth_kwargs
from app.services.market_outlook import outlook

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE: Dict[str, tuple] = {}
_LOCK = threading.Lock()
_TTL = 1800.0


def _jataka_plan(kw: Dict) -> Optional[Dict]:
    if not (kw.get("date") and kw.get("time")):
        return None
    try:
        with _CHART_LOCK:  # swisseph sidereal mode is process-global
            rep = _engine.full_report(**kw)
        plan = rep.get("plan") or {}
        return None if "error" in plan else plan
    except Exception as e:  # the plan is a refinement; never fail the outlook over it
        logger.warning("outlook jataka plan failed: %s", e)
        return None


@router.get("/outlook")
def get_outlook(date_: Optional[str] = Query(None, alias="date"), capital: float = 500000.0,
                name: str = "", birth_date: str = "", time_: str = Query("", alias="time"), place: str = "",
                lat: Optional[float] = None, lon: Optional[float] = None, tz: Optional[float] = None,
                tz_name: str = "", node: str = "mean", ayanamsa: str = "lahiri"):
    try:
        start = date.fromisoformat(date_[:10]) if date_ else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    kw = birth_kwargs(name, birth_date, time_, place, lat, lon, tz, tz_name, node, ayanamsa)
    key = f"{start}|{capital}|{sorted(kw.items())}"
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]
    try:
        plan = _jataka_plan(kw)
        out = outlook(_market, start, plan, capital)
        out["jataka"] = ({"name": kw["name"] or "your chart", "used": True} if plan else {"used": False})
        out = _clean(out)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("outlook failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    with _LOCK:
        _CACHE[key] = (time.time(), out)
        if len(_CACHE) > 32:
            _CACHE.pop(next(iter(_CACHE)))
    return out
