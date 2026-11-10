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


@router.get("/income-lab")
def get_income_lab(symbol: str = "^NSEI", strategy: str = "put_spread", risk: float = 0.05,
                   start: str = "2009-01-01"):
    """Weekly premium-selling back-test with and without astrological filters (v1.7)."""
    from app.services.income_lab import run
    try:
        return _clean(run(_market, symbol, strategy, risk, start))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("income lab failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/brief")
def get_brief(lat: float = 19.076, lon: float = 72.8777, tz: float = 5.5, place: str = "Mumbai (NSE / BSE)"):
    """Today's one-glance brief: day tone, week's market lean, and this week's income trade (v1.7)."""
    from datetime import datetime, timedelta, timezone as _tz
    from app.services.income_lab import run as lab_run
    from app.services.panchang import panchang

    today = datetime.now(_tz(timedelta(hours=tz))).date()
    out: Dict = {"success": True, "date": today.isoformat(), "place": place}
    try:
        p = panchang(today, lat, lon, tz, place)
        out["day"] = {"tone": p["tone"], "vara": p["vara"], "tithi": p["tithi"]["label"],
                      "nakshatra": p["nakshatra"]["name"], "rahu_kaal": p["rahu_kaal"],
                      "abhijit": p["abhijit"], "flags": p["flags"], "plain_english": p["plain_english"]}
    except Exception as e:
        logger.warning("brief panchang failed: %s", e)
        out["day"] = None
    try:
        o = outlook(_market, today, None, 500000.0)
        wk = o["horizons"]["week"]["sectors"]
        lean = sum(s["z"] for s in wk) / len(wk)
        backed = [s for s in wk if s["direction"] != "range" and s["backtest"].get("verdict") in ("significant edge", "weak hint")]
        out["week"] = {"lean": "up" if lean > 0.25 else ("down" if lean < -0.25 else "range"), "lean_z": round(lean, 2),
                       "strongest": wk[0]["sector"], "weakest": wk[-1]["sector"],
                       "backed": [{"sector": s["sector"], "direction": s["direction"], "verdict": s["backtest"]["verdict"]} for s in backed],
                       "summary": o["horizons"]["week"]["summary"]}
    except Exception as e:
        logger.warning("brief outlook failed: %s", e)
        out["week"] = None
    try:
        lab = lab_run(_market, "^NSEI", "put_spread", 0.05)
        if lab.get("success"):
            base = lab["results"][0]
            out["trade"] = {**lab["this_week"], "strategy": lab["strategy_label"],
                            "win_rate_pct": base["win_rate_pct"], "worst_week_on_margin_pct": base["worst_week_on_margin_pct"],
                            "positive_months_pct": base["positive_months_pct"]}
        else:
            out["trade"] = None
    except Exception as e:
        logger.warning("brief lab failed: %s", e)
        out["trade"] = None
    out["disclaimer"] = "Educational summary of the sections below. Not financial advice."
    return _clean(out)
