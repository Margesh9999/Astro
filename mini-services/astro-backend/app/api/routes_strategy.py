"""v1.3 strategy endpoints (mounted under /api/v1 by app.main).

- GET /strategy/agents/{symbol}  — TradingAgents-style debate (also served at /agents/{symbol})
- GET /strategy/final/{symbol}   — Final Strategy: every signal → one 30/60/90/365-day plan

Every input is gathered inside its own try/except so one failing service
never breaks the output; unavailable inputs are reported honestly.
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException

from app.services.agents import TradingAgentsEngine
from app.services import agents_news
from app.services import final_strategy as fs

logger = logging.getLogger(__name__)
router = APIRouter()
engine = TradingAgentsEngine()

_CACHE: Dict[Tuple, Tuple[float, Any]] = {}
_TTL = 120.0


def _routes():
    # lazy import: routes.py imports this module's builder for /agents/{symbol}
    from app.api import routes
    return routes


def clean(o: Any) -> Any:
    """Recursively make a payload JSON-safe (NaN/Inf → None, numpy → python, datetimes → iso)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, datetime):
        return o.isoformat()
    return o


def _cached(key: Tuple):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    return None


def _store(key: Tuple, val: Any):
    if len(_CACHE) > 64:
        _CACHE.clear()
    _CACHE[key] = (time.time(), val)


def _days_ahead(date_s: str) -> int:
    try:
        return (datetime.strptime(str(date_s)[:10], "%Y-%m-%d").date() - datetime.utcnow().date()).days
    except Exception:
        return 999


async def gather(symbol: str, capital: float, name: str = "", date: str = "", time_: str = "",
                 place: str = "") -> Dict:
    """Collect every signal for the symbol. Returns ctx + status per input."""
    r = _routes()
    status: Dict[str, str] = {}
    ctx: Dict[str, Any] = {"symbol": symbol}

    try:
        info = r.market_service.get_symbol_info(symbol)
        ctx["symbol_name"] = info.get("name", symbol) if isinstance(info, dict) else symbol
    except Exception:
        ctx["symbol_name"] = symbol

    # technical / analytics pack
    try:
        pack = await r.get_analytics_charts(symbol)
        fc = pack.get("forecast") or {}
        vol = pack.get("volatility") or {}
        vnow, vmed = fs._n(vol.get("now_pct")), fs._n(vol.get("median_pct"))
        ctx["analytics"] = {
            "signal": fc.get("signal"), "levels": fc.get("levels"), "mc": fc.get("mc_summary") or {
                k: v for k, v in (fc.get("mc") or {}).items() if not isinstance(v, list)},
            "rsi": (pack.get("rsi") or {}).get("now"),
            "pct_b": (pack.get("bollinger") or {}).get("pct_b"),
            "atr_pct": (pack.get("atr") or {}).get("now_pct"),
            "sigma_pct": (pack.get("distribution") or {}).get("sigma_pct"),
            "vol_now_pct": vnow, "vol_median_pct": vmed,
            "vol_ratio": (vnow / vmed) if vnow and vmed else 1.0,
            "regime": (pack.get("memory") or {}).get("regime"), "hurst": (pack.get("memory") or {}).get("hurst"),
            "invalidation": fc.get("invalidation"),
        }
        ctx["perf"] = pack.get("performance") or {}
        status["technical"] = "ok"
    except Exception as e:
        logger.warning("strategy: analytics unavailable for %s: %s", symbol, e)
        ctx["analytics"] = {}; ctx["perf"] = {}
        status["technical"] = f"unavailable ({e.__class__.__name__})"

    try:
        sraw = await r.get_quant_stats(symbol, 3)
        ctx["stats"] = sraw.get("stats") or {}
        status["quant"] = "ok"
    except Exception as e:
        ctx["stats"] = {}; status["quant"] = f"unavailable ({e.__class__.__name__})"
    try:
        rraw = await r.get_quant_risk(symbol, 3, 0.95, float(capital))
        ctx["risk"] = rraw.get("risk") or {}
    except Exception:
        ctx["risk"] = {}

    try:
        astro = await r.get_astro_signal(symbol)
        for a in astro.get("timing_alerts") or []:
            a["days_ahead"] = _days_ahead(a.get("date"))
        ctx["astro"] = astro
        ctx["spot"] = fs._n(astro.get("spot"))
        status["suri"] = "ok"
    except Exception as e:
        ctx["astro"] = {}; status["suri"] = f"unavailable ({e.__class__.__name__})"
    if not ctx.get("spot"):
        try:
            h = r.market_service.fetch_historical_data(symbol, period="1mo", interval="1d")
            ctx["spot"] = float(h["Close"].dropna().iloc[-1])
        except Exception:
            ctx["spot"] = 0.0

    try:
        ev = await r.get_events_forecast(symbol=symbol, days=90)
        events = ev.get("events") or []
        for e in events:
            e["days_ahead"] = _days_ahead(e.get("date"))
        ctx["events"] = events
        status["sky"] = "ok"
    except Exception as e:
        ctx["events"] = []; status["sky"] = f"unavailable ({e.__class__.__name__})"

    # jataka: natal chart, strengths, dasha
    ctx["chart"] = None
    try:
        je = r.jataka_engine
        chart = je.compute_chart(name=name, date=date, time=time_, place=place)
        ctx["chart"] = chart
        ctx["strengths"] = je.strengths(chart["positions"])
        d = chart["dasha"]
        cur = d.current()
        md, ad, pd_ = cur.get("mahadasha"), cur.get("antardasha"), cur.get("pratyantardasha")
        ctx["dasha"] = {
            "md": md["lord"] if md else None, "ad": ad["lord"] if ad else None,
            "pd": pd_["lord"] if pd_ else None,
            "md_end": md["end"].strftime("%Y-%m-%d") if md else None,
            "ad_end": ad["end"].strftime("%Y-%m-%d") if ad else None,
            "pd_end": pd_["end"].strftime("%Y-%m-%d") if pd_ else None,
            "favour": je._dasha_favour(md["lord"]) if md else 1.0,
            "ad_favour": je._dasha_favour(ad["lord"]) if ad else 1.0,
            "interpretation": d.interpretation(),
        }
        status["jataka"] = "ok"
    except Exception as e:
        logger.warning("strategy: jataka unavailable: %s", e)
        ctx["strengths"] = None; ctx["dasha"] = {}
        status["jataka"] = f"unavailable ({e.__class__.__name__})"

    ctx["news"] = agents_news.fetch_news(symbol)
    ctx["fundamentals"] = agents_news.fetch_fundamentals(symbol)
    status["news"] = "ok" if ctx["news"].get("available") else "unavailable (no news feed)"
    return {"ctx": ctx, "status": status}


async def build_agents(symbol: str, rounds: int = 2, capital: float = 50000.0, llm: bool = False,
                       g: Optional[Dict] = None) -> Dict:
    key = ("agents", symbol, rounds, round(capital), llm)
    hit = _cached(key)
    if hit is not None and g is None:
        return hit
    g = g or await gather(symbol, capital)
    ctx = g["ctx"]
    res = engine.analyse(symbol, ctx.get("symbol_name", symbol), ctx, rounds=rounds, capital=capital)
    from app.services import agents_llm
    res["llm_available"] = agents_llm.available()
    if llm:
        try:
            res = engine.apply_llm(res)
        except Exception as e:
            logger.info("LLM mode failed, keeping rules: %s", e)
            res["mode"] = "rules (LLM unavailable — fell back)"
    res["inputs_status"] = g["status"]
    res = clean(res)
    _store(key, res)
    return res


@router.get("/strategy/agents/{symbol}")
async def strategy_agents(symbol: str, rounds: int = 2, capital: float = 50000.0, llm: bool = False):
    try:
        return await build_agents(symbol, rounds, capital, llm)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("agents error")
        raise HTTPException(status_code=500, detail=str(e))


def _ml_input(symbol: str) -> Dict:
    """Use the cached full-history model-zoo result for this symbol if one exists (never trains here)."""
    try:
        from app.api import routes_models
        res = routes_models._load_cached(symbol, True) or routes_models._load_cached(symbol, False)
        if not res or not res.get("success"):
            return {"available": False, "reason": "Not trained yet — train the model zoo (Model Lab) to include ML in this plan."}
        board = res.get("leaderboard") or []
        best = next((r for r in board if r.get("key") == res.get("best_model")), {})
        r2 = fs._n(best.get("r2_os") if best.get("r2_os") is not None else best.get("cv_r2"))
        h20 = next((h for h in (res.get("forecast") or {}).get("horizons", []) if h.get("horizon") == 20), None)
        score, fc_txt = 0.0, ""
        if h20:
            exp = fs._n(h20.get("expected_return_pct"))
            p_up = fs._n(h20.get("p_up"), 0.5)
            base = fs._n(h20.get("hist_up_share"), 0.5)
            # skill-weighted: the edge over the historical up-share drives the score, kept small
            score = fs._clip((p_up - base) * 400 + exp * 5)
            fc_txt = f"; 20-day ensemble {exp:+.2f}%, P(up) {p_up:.0%} vs {base:.0%} historically"
        days = (res.get("data") or {}).get("rows") or (res.get("data") or {}).get("n_rows")
        return {"available": True, "score": score,
                "reason": f"Best model {res.get('best_name') or res.get('best_model')} over {days or 'full-history'} sessions{fc_txt}. "
                          "Out-of-sample skill is near zero, so ML is a small tilt, not a trigger."}
    except Exception as e:
        return {"available": False, "reason": f"ML input unavailable ({e.__class__.__name__})."}


@router.get("/strategy/final/{symbol}")
async def final_strategy(symbol: str, name: str = "", date: str = "", time: str = "", place: str = "",
                         capital: float = 50000.0, target_weekly: float = 500.0):
    """Final Strategy: natal vs today, signal scoreboard, 30/60/90/365-day plans and an
    illustrative income plan for the selected stock."""
    try:
        capital = max(1000.0, min(1e9, float(capital or 50000)))
        target_weekly = max(10.0, min(1e6, float(target_weekly or 500)))
        key = ("final", symbol, name, date, time, place, round(capital), round(target_weekly))
        hit = _cached(key)
        if hit is not None:
            return hit
        g = await gather(symbol, capital, name, date, time, place)
        ctx, status = g["ctx"], g["status"]
        sym_name = ctx.get("symbol_name", symbol)
        spot = fs._n(ctx.get("spot"))

        try:
            agents = await build_agents(symbol, 2, capital, False, g=g)
            status["agents"] = "ok"
        except Exception as e:
            agents = None; status["agents"] = f"unavailable ({e.__class__.__name__})"

        ml = _ml_input(symbol)
        status["ml"] = "ok" if ml.get("available") else "not trained"

        transits = None
        r = _routes()
        if ctx.get("chart"):
            try:
                transits = fs.natal_vs_today(ctx["chart"]["positions"], ctx.get("strengths") or {}, r.jataka_engine.vedic)
                status["transits"] = "ok"
            except Exception as e:
                logger.warning("strategy: transits failed: %s", e)
                status["transits"] = f"unavailable ({e.__class__.__name__})"

        rows = fs.scoreboard({
            "analytics": ctx.get("analytics"), "stats": ctx.get("stats"), "ml": ml,
            "astro": ctx.get("astro"), "events": ctx.get("events") if status.get("sky") == "ok" else None,
            "agents": agents, "natal": ctx.get("strengths"), "dasha": ctx.get("dasha"), "transits": transits,
        })
        score = fs.overall(rows)

        try:
            extra = fs.slow_planet_dates(365)
        except Exception as e:
            logger.warning("strategy: slow planet scan failed: %s", e); extra = []
        key_dates = fs.build_key_dates(ctx.get("events"), (ctx.get("astro") or {}).get("timing_alerts"),
                                       (ctx.get("chart") or {}).get("dasha"), extra)

        planner = None
        try:
            planner = r.income_planner.plan(capital=capital, target_weekly=target_weekly, focus="global")
            status["income_planner"] = "ok"
        except Exception as e:
            status["income_planner"] = f"unavailable ({e.__class__.__name__})"
        income = fs.income_section(planner, capital, target_weekly, ctx.get("dasha"), [])
        plans = fs.horizon_plans(rows, spot, ctx.get("analytics") or {}, key_dates, capital, ctx.get("dasha") or {}, income)
        income = fs.income_section(planner, capital, target_weekly, ctx.get("dasha"), plans)
        routine = fs.weekly_routine(sym_name, key_dates, plans, income)

        chart = ctx.get("chart") or {}
        birth = chart.get("birth") or {}
        out = {
            "success": True, "symbol": symbol, "symbol_name": sym_name, "spot": spot,
            "as_of": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "birth": birth,
            "inputs_status": status,
            "overall": {"score": score, "signal": fs._sig(score), "stance": fs._stance(score),
                        "bullish": sum(1 for x in rows if x["available"] and x["signal"] == "bullish"),
                        "bearish": sum(1 for x in rows if x["available"] and x["signal"] == "bearish"),
                        "neutral": sum(1 for x in rows if x["available"] and x["signal"] == "neutral"),
                        "available": sum(1 for x in rows if x["available"])},
            "scoreboard": rows,
            "natal_vs_today": transits,
            "dasha": {k: v for k, v in (ctx.get("dasha") or {}).items()},
            "agents_decision": (agents or {}).get("decision"),
            "agents_plain_english": (agents or {}).get("plain_english"),
            "ml": ml,
            "key_dates": key_dates[:40],
            "plans": plans,
            "income": income,
            "weekly_routine": routine,
            "bottom_line": fs.bottom_line(sym_name, score, plans, income, transits, ctx.get("dasha"), rows),
            "risk_warning": ("Illustrative only. Income figures are modelled averages from historical yield ranges — "
                             "NOT guaranteed. Option selling and leveraged strategies can lose more than the premium "
                             "collected; losing weeks and drawdowns are normal. Astrological inputs have no proven "
                             "predictive value. Educational tool — not financial advice."),
        }
        out = clean(out)
        _store(key, out)
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("final strategy error")
        raise HTTPException(status_code=500, detail=str(e))
