"""
OpenBB-style `forecast` menu baselines with an honest rolling-origin
backtest: Naive, Drift, Simple Exponential Smoothing, Holt (damped trend),
ARIMA(1,1,1) and Theta — fitted on log prices, forecasting 20 trading days.
"""
from __future__ import annotations

import logging
import warnings
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd

from app.services.quant_common import clean, insight, naive, r

logger = logging.getLogger(__name__)
H = 20


def _naive(y: np.ndarray, h: int) -> np.ndarray:
    return np.repeat(y[-1], h)


def _drift(y: np.ndarray, h: int) -> np.ndarray:
    slope = (y[-1] - y[0]) / max(1, len(y) - 1)
    return y[-1] + slope * np.arange(1, h + 1)


def _ses(y: np.ndarray, h: int) -> np.ndarray:
    """Simple exponential smoothing; alpha chosen by grid-search on one-step SSE (fast, no optimiser)."""
    from scipy.signal import lfilter
    best_sse, best_level = np.inf, y[-1]
    for a in np.linspace(0.05, 1.0, 20):
        lvl, _ = lfilter([a], [1, -(1 - a)], y, zi=[(1 - a) * y[0]])
        sse = float(np.sum((y[1:] - lvl[:-1]) ** 2))
        if sse < best_sse:
            best_sse, best_level = sse, lvl[-1]
    return np.repeat(best_level, h)


def _holt(y: np.ndarray, h: int, phi: float = 0.98) -> np.ndarray:
    """Damped-trend Holt; (alpha, beta) by grid-search on one-step SSE over the last 250 points."""
    z = y[-250:]
    best = (np.inf, z[-1], 0.0)
    for a in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0):
        for b in (0.01, 0.05, 0.1, 0.2):
            lv, tr, sse = z[0], z[1] - z[0], 0.0
            for t in range(1, len(z)):
                pred = lv + phi * tr
                e = z[t] - pred
                sse += e * e
                lv_new = pred + a * e
                tr = phi * tr + a * b * e
                lv = lv_new
            if sse < best[0]:
                best = (sse, lv, tr)
    _, lv, tr = best
    damp = np.cumsum(phi ** np.arange(1, h + 1))
    return lv + damp * tr


def _arima(y: np.ndarray, h: int) -> np.ndarray:
    from statsmodels.tsa.arima.model import ARIMA
    return ARIMA(y, order=(1, 1, 1), trend="t").fit().forecast(h)


def _theta(y: np.ndarray, h: int) -> np.ndarray:
    from statsmodels.tsa.forecasting.theta import ThetaModel
    return np.asarray(ThetaModel(y, period=1, deseasonalize=False).fit().forecast(h))


MODELS: List[Tuple[str, Callable, str]] = [
    ("Naive", _naive, "Tomorrow = today. The random-walk benchmark every model must beat."),
    ("Drift", _drift, "Extends the average historical slope — the 'trend continues' baseline."),
    ("SES", _ses, "Simple exponential smoothing: a weighted average of recent prices, no trend."),
    ("Holt (damped)", _holt, "Exponential smoothing with a trend that fades out over the horizon."),
    ("ARIMA(1,1,1)", _arima, "Classic autoregressive model of daily changes with drift."),
    ("Theta", _theta, "M3-competition winner: blends a long-run trend line with exponential smoothing."),
]


def build_forecast(df: pd.DataFrame, symbol: str, fit_days: int = 504, origins: int = 5) -> Dict:
    d = naive(df)
    close = d["Close"]
    if len(close) < 300:
        return {"success": False, "error": "need at least ~15 months of daily history"}
    y_all = np.log(close.to_numpy())
    n = len(y_all)
    errs: Dict[str, List[Tuple[float, bool]]] = {m[0]: [] for m in MODELS}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for k in range(origins, 0, -1):
            end = n - k * H
            if end - fit_days < 50:
                continue
            train = y_all[max(0, end - fit_days):end]
            actual = y_all[end:end + H]
            for name, fn, _ in MODELS:
                try:
                    f = np.asarray(fn(train, H))
                    ape = float(np.mean(np.abs(np.exp(f) / np.exp(actual) - 1)) * 100)
                    move = f[-1] - train[-1]
                    dir_ok = (None if abs(move) < 1e-9 else
                              bool(np.sign(move) == np.sign(actual[-1] - train[-1])))
                    errs[name].append((ape, dir_ok))
                except Exception as e:  # model failed to converge — skip that origin
                    logger.debug(f"{name} failed: {e}")
        train = y_all[-fit_days:]
        fc = {}
        for name, fn, _ in MODELS:
            try:
                fc[name] = np.exp(np.asarray(fn(train, H)))
            except Exception as e:
                logger.warning(f"forecast {name} failed for {symbol}: {e}")
        band = None
        try:
            from statsmodels.tsa.arima.model import ARIMA
            gf = ARIMA(train, order=(1, 1, 1), trend="t").fit().get_forecast(H)
            ci = np.exp(gf.conf_int(alpha=0.2))
            band = (ci[:, 0], ci[:, 1])
        except Exception:
            pass

    table = []
    for name, _, desc in MODELS:
        e = errs[name]
        if not e or name not in fc:
            continue
        table.append({"model": name, "description": desc,
                      "mape": r(np.mean([x[0] for x in e]), 2),
                      "direction_hit": (r(100 * np.mean([x[1] for x in e if x[1] is not None]), 0)
                                        if any(x[1] is not None for x in e) else None),
                      "tests": len(e),
                      "forecast_end": r(fc[name][-1], 2),
                      "change_pct": r((fc[name][-1] / close.iloc[-1] - 1) * 100, 2)})
    if not table:
        return {"success": False, "error": "forecast models failed"}
    table.sort(key=lambda x: x["mape"] if x["mape"] is not None else 1e9)
    naive_mape = next((t["mape"] for t in table if t["model"] == "Naive"), None)
    best = table[0]
    wts = {t["model"]: 1 / max(t["mape"], 1e-3) for t in table}
    ens = sum(fc[m] * w for m, w in wts.items()) / sum(wts.values())
    beats = [t["model"] for t in table if naive_mape and t["mape"] < naive_mape * 0.97]

    future = pd.bdate_range(close.index[-1] + pd.Timedelta(days=1), periods=H)
    hist = close.iloc[-120:]
    series = {"dates": [str(x.date()) for x in hist.index] + [str(x.date()) for x in future],
              "close": [r(v, 2) for v in hist] + [None] * H}
    for m in fc:
        series[m] = [None] * (len(hist) - 1) + [r(close.iloc[-1], 2)] + [r(v, 2) for v in fc[m]]
    series["Ensemble"] = [None] * (len(hist) - 1) + [r(close.iloc[-1], 2)] + [r(v, 2) for v in ens]
    if band is not None:
        series["lo80"] = [None] * (len(hist) - 1) + [r(close.iloc[-1], 2)] + [r(v, 2) for v in band[0]]
        series["hi80"] = [None] * (len(hist) - 1) + [r(close.iloc[-1], 2)] + [r(v, 2) for v in band[1]]
    ens_chg = float(ens[-1] / close.iloc[-1] - 1) * 100
    lo_b = float(band[0][-1]) if band is not None else None
    hi_b = float(band[1][-1]) if band is not None else None
    return clean({
        "success": True, "symbol": symbol, "horizon_days": H, "table": table,
        "best": best["model"], "ensemble_change_pct": r(ens_chg, 2),
        "band80_end": [r(lo_b, 2), r(hi_b, 2)] if band is not None else None,
        "series": series,
        "insight": insight(
            f"Six classical forecasting baselines (OpenBB forecast menu) fitted to ~2 years of prices, each projecting {H} trading days; "
            f"accuracy checked on {best['tests']} rolling past windows.",
            f"Most accurate recently: {best['model']} (average error {best['mape']:.2f}%"
            + (f", right direction {best['direction_hit']:.0f}% of the time). " if best["direction_hit"] is not None else "). ")
            + (f"Only {', '.join(beats)} beat the naive 'no-change' guess." if beats else
               "No model beat the naive 'no-change' guess — prices behaved like a random walk.")
            + f" The error-weighted ensemble points to {ens_chg:+.1f}% in {H} days"
            + (f", with an 80% ARIMA band of {lo_b:,.2f}–{hi_b:,.2f}." if band is not None else "."),
            ("The models add little over a coin-flip — use the band as a planning range, not as a target; let the Signals tab decide direction."
             if not beats else
             f"{best['model']} has a small measurable edge; treat its direction as one vote alongside trend signals, never as a price promise."),
        ),
    })
