"""v1.3 models endpoints (mounted under /api/v1 by app.main).

POST /models/zoo/train   start (or reuse) a background full-history zoo run
GET  /models/zoo/status  poll progress / fetch the finished result
GET  /models/zoo/catalog every model in the zoo, grouped by family
POST /models/backtest    walk-forward equity curve for any zoo model / ensemble vs buy & hold
"""
from __future__ import annotations

import json
import logging
import math
import os
import pickle
import threading
import time
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.market_data import MarketDataService
from app.services.model_features import load_dataset
from app.services.model_zoo import (REGRESSORS, ModelZoo, build_model, catalog, run_zoo,
                                    select_cols)

logger = logging.getLogger(__name__)
router = APIRouter()
_market = MarketDataService(cache_dir=settings.ASTRO_CACHE_DIR)

_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_ART: Dict[str, Dict[str, Any]] = {}   # in-memory OOS artifacts for the backtest


def _clean(o: Any) -> Any:
    """Recursively replace NaN/Inf and numpy scalars so FastAPI can serialise."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _key(symbol: str, vedic: bool) -> str:
    return f"{symbol}|{int(vedic)}"


def _paths(symbol: str, vedic: bool):
    safe = symbol.replace("^", "idx_").replace(".", "_").replace("=", "_").replace("/", "_")
    base = os.path.join(settings.ASTRO_CACHE_DIR, f"zoo13_{safe}_{int(vedic)}")
    return base + ".json", base + ".pkl"


def _load_cached(symbol: str, vedic: bool) -> Optional[Dict[str, Any]]:
    jp, _ = _paths(symbol, vedic)
    if os.path.exists(jp):
        try:
            with open(jp) as fh:
                return json.load(fh)
        except Exception:
            return None
    return None


def _load_art(symbol: str, vedic: bool) -> Optional[Dict[str, Any]]:
    k = _key(symbol, vedic)
    if k in _ART:
        return _ART[k]
    _, pp = _paths(symbol, vedic)
    if os.path.exists(pp):
        try:
            with open(pp, "rb") as fh:
                _ART[k] = pickle.load(fh)
                return _ART[k]
        except Exception:
            return None
    return None


def _run_job(symbol: str, vedic: bool):
    k = _key(symbol, vedic)
    job = _JOBS[k]
    try:
        job.update(stage="building full-history planetary + technical features", progress=2)
        df, _stamp = load_dataset(_market, symbol, vedic)
        if df.empty or len(df) < 400:
            raise ValueError(f"not enough price history for {symbol} ({len(df)} sessions)")
        job["rows"] = int(len(df) - 1)

        def cb(stage: str, done: int, total: int):
            job["stage"] = stage
            job["progress"] = int(5 + 93 * done / max(total, 1))
            job["done"] = done
            job["total"] = total

        out = run_zoo(df, symbol, vedic, progress=cb)
        res = _clean(out["result"])
        art = {"oos": out["oos"], "test_idx": out["test_idx"], "dates": out["dates"], "y": out["y"],
               "best_model": res.get("best_model"), "members": res.get("ensemble_members", []),
               "names": {r["key"]: r["name"] for r in res["leaderboard"] + res["classifiers"]}}
        _ART[k] = art
        jp, pp = _paths(symbol, vedic)
        try:
            os.makedirs(settings.ASTRO_CACHE_DIR, exist_ok=True)
            with open(jp, "w") as fh:
                json.dump(res, fh, allow_nan=False)
            with open(pp, "wb") as fh:
                pickle.dump(art, fh)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"zoo cache write failed: {exc}")
        job.update(stage="done", progress=100, result=res)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"zoo job {k} failed")
        job.update(stage="failed", error=str(exc))


class ZooRequest(BaseModel):
    symbol: str = "^GSPC"
    use_vedic: bool = True
    force: bool = False


@router.post("/models/zoo/train")
async def zoo_train(req: ZooRequest):
    k = _key(req.symbol, req.use_vedic)
    with _LOCK:
        job = _JOBS.get(k)
        if job and job["stage"] not in ("done", "failed"):
            return {"status": "running", "stage": job["stage"], "progress": job["progress"]}
        if not req.force:
            if job and job["stage"] == "done":
                return {"status": "done", **job["result"]}
            cached = _load_cached(req.symbol, req.use_vedic)
            if cached:
                return {"status": "done", "cached": True, **cached}
        _JOBS[k] = {"stage": "starting", "progress": 1, "result": None, "error": None,
                    "started": time.time()}
    threading.Thread(target=_run_job, args=(req.symbol, req.use_vedic), daemon=True).start()
    return {"status": "started", "stage": "starting", "progress": 1}


@router.get("/models/zoo/status")
async def zoo_status(symbol: str = "^GSPC", vedic: bool = True):
    job = _JOBS.get(_key(symbol, vedic))
    if job:
        if job["stage"] == "failed":
            return {"status": "failed", "error": job["error"]}
        if job["stage"] == "done":
            return {"status": "done", **job["result"]}
        return {"status": "running", "stage": job["stage"], "progress": job["progress"],
                "done": job.get("done", 0), "total": job.get("total", 0), "rows": job.get("rows"),
                "elapsed": round(time.time() - job["started"], 1)}
    cached = _load_cached(symbol, vedic)
    if cached:
        return {"status": "done", "cached": True, **cached}
    return {"status": "idle"}


@router.get("/models/zoo/catalog")
async def zoo_catalog():
    return {"models": catalog(), "count": len(catalog())}


# ---------------------------------------------------------------------------
# Backtest on honest out-of-sample predictions
# ---------------------------------------------------------------------------
class BacktestReq(BaseModel):
    symbol: str = "^GSPC"
    use_vedic: bool = True
    model: str = "ens_avg"            # ens_avg | ens_stack | best | <regressor key> | <classifier key>_1
    cost_bps: float = Field(5.0, ge=0, le=100)
    mode: str = "long_cash"           # long_cash | long_short


def _quick_art(symbol: str, vedic: bool) -> Dict[str, Any]:
    """No zoo run yet: fast walk-forward with Ridge + HistGB on the full history."""
    df, _ = load_dataset(_market, symbol, vedic)
    if df.empty or len(df) < 400:
        raise HTTPException(status_code=400, detail="Not enough history for a walk-forward backtest")
    z = ModelZoo(df, n_jobs=1)
    spec_by = {s.key: s for s in REGRESSORS}
    for k in ("ridge", "hgb"):
        s = spec_by[k]
        X = z.X[:, select_cols(z.feats, s.fset)]
        preds = []
        for tr, te in z.folds:
            m = build_model(s)
            m.fit(X[tr], z.y[tr])
            preds.append(np.ravel(m.predict(X[te])))
        z.oos[k] = np.concatenate(preds)
    z.oos["ens_avg"] = (z.oos["ridge"] + z.oos["hgb"]) / 2
    return {"oos": z.oos, "test_idx": z.test_idx, "dates": z.df.index, "y": z.y, "best_model": "ens_avg",
            "members": ["ridge", "hgb"], "quick": True,
            "names": {"ridge": "Ridge", "hgb": "Histogram gradient boosting", "ens_avg": "Average of Ridge + HistGB"}}


def _metrics(r: np.ndarray, eq: np.ndarray) -> Dict[str, Optional[float]]:
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    active = r[r != 0]
    return {"total_return": float(eq[-1] - 1) * 100,
            "annual_return": float(eq[-1] ** (1 / max(years, 1e-9)) - 1) * 100,
            "sharpe": float(np.mean(r) / (np.std(r) + 1e-12) * np.sqrt(252)),
            "max_drawdown": float(np.min(eq / peak - 1)) * 100,
            "win_rate": float((active > 0).mean() * 100) if len(active) else None}


@router.post("/models/backtest")
async def models_backtest(req: BacktestReq):
    art = _load_art(req.symbol, req.use_vedic)
    quick = False
    if art is None:
        art = _quick_art(req.symbol, req.use_vedic)
        quick = True
    key = art.get("best_model") if req.model == "best" else req.model
    oos = art["oos"]
    if key not in oos:
        key = "ens_avg" if "ens_avg" in oos else next(iter(oos))
    p = np.asarray(oos[key], float)
    y = np.asarray(art["y"], float)[art["test_idx"]]
    dates = pd.DatetimeIndex(art["dates"])[art["test_idx"]]
    is_clf = key.endswith("_1") or key.endswith("_5")
    if is_clf:
        sig = np.where(p > 0.5, 1.0, -1.0 if req.mode == "long_short" else 0.0)
        rule = "long when the classifier's P(up) > 50%" + (", short otherwise" if req.mode == "long_short" else ", cash otherwise")
    else:
        sig = np.where(p > 0, 1.0, -1.0 if req.mode == "long_short" else 0.0)
        rule = "long when the predicted return > 0" + (", short otherwise" if req.mode == "long_short" else ", cash otherwise")
    turns = np.abs(np.diff(np.concatenate([[0.0], sig])))
    strat = sig * y - turns * req.cost_bps / 10000.0
    eq_s, eq_b = np.cumprod(1 + strat), np.cumprod(1 + y)
    s_m, b_m = _metrics(strat, eq_s), _metrics(y, eq_b)
    s_m["exposure"] = float(np.mean(sig != 0) * 100)
    s_m["trades"] = int((turns > 0).sum())
    # calendar-year comparison
    yr = pd.DataFrame({"s": strat, "b": y}, index=dates)
    ann = (1 + yr).groupby(yr.index.year).prod() - 1
    years_beat = int((ann["s"] > ann["b"]).sum())
    step = max(1, len(dates) // 400)
    idx = list(range(0, len(dates), step))
    if idx[-1] != len(dates) - 1:
        idx.append(len(dates) - 1)
    curve = [{"date": str(dates[i].date()), "strategy": float(eq_s[i] * 100), "buy_hold": float(eq_b[i] * 100)}
             for i in idx]
    name = art.get("names", {}).get(key, key)
    diff_cagr = s_m["annual_return"] - b_m["annual_return"]
    dd_better = s_m["max_drawdown"] > b_m["max_drawdown"]
    if diff_cagr > 0.5 and s_m["sharpe"] > b_m["sharpe"]:
        verdict = (f"{name} beat buy-and-hold out of sample by {diff_cagr:+.1f}%/yr with a better Sharpe "
                   f"({s_m['sharpe']:.2f} vs {b_m['sharpe']:.2f}). Promising, but check it holds in the most recent "
                   "decade before trusting it, and size small.")
    elif s_m["sharpe"] > b_m["sharpe"] and dd_better:
        verdict = (f"{name} returned {diff_cagr:+.1f}%/yr relative to buy-and-hold, with a smaller worst drawdown "
                   f"({s_m['max_drawdown']:.0f}% vs {b_m['max_drawdown']:.0f}%) — a risk-reducer, not a return-booster. "
                   "Useful only as a tilt on exposure.")
    else:
        verdict = (f"{name} trailed buy-and-hold by {abs(diff_cagr):.1f}%/yr (Sharpe {s_m['sharpe']:.2f} vs "
                   f"{b_m['sharpe']:.2f}) after {req.cost_bps:g} bp costs. Don't trade it — simply holding the "
                   "stock did better over this out-of-sample history.")
    verdict += f" It beat buy-and-hold in {years_beat} of {len(ann)} calendar years and was invested {s_m['exposure']:.0f}% of the time."
    options = [{"key": "ens_avg", "name": art.get("names", {}).get("ens_avg", "Ensemble (average of top models)")}]
    if "ens_stack" in oos:
        options.append({"key": "ens_stack", "name": "Stacked ensemble"})
    if art.get("best_model") and art["best_model"] in oos:
        options.append({"key": "best", "name": f"Zoo winner — {art.get('names', {}).get(art['best_model'], art['best_model'])}"})
    for k in oos:
        if k in ("ens_avg", "ens_stack") or k.startswith("naive_"):
            continue
        options.append({"key": k, "name": art.get("names", {}).get(k[:-2] if k.endswith(("_1", "_5")) and k[:-2] in art.get("names", {}) else k, k)
                        + (" (1d direction)" if k.endswith("_1") else " (5d direction)" if k.endswith("_5") else "")})
    options = [o for o in options if not o["key"].endswith("_5")]  # 5d classifiers overlap daily — exclude
    return _clean({
        "success": True, "symbol": req.symbol, "vedic": req.use_vedic, "model": key, "model_name": name,
        "source": "quick walk-forward (Ridge + HistGB) — run the Model Zoo for every model" if quick
        else "Model Zoo out-of-sample predictions",
        "rule": rule, "cost_bps": req.cost_bps, "mode": req.mode,
        "test_range": f"{dates[0].date()} to {dates[-1].date()}", "test_samples": int(len(y)),
        "test_years": round((dates[-1] - dates[0]).days / 365.2425, 1),
        "strategy": s_m, "buy_hold": b_m, "years_beat": years_beat, "years_total": int(len(ann)),
        "equity_curve": curve, "verdict": verdict, "options": options,
        "disclaimer": "Out-of-sample walk-forward simulation; educational only, not financial advice.",
    })
