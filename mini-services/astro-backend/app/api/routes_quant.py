"""v1.3 quant endpoints (mounted under /api/v1 by app.main).

  GET /quant/signals/{symbol}    classic strategy signal board + backtests + consensus
  GET /quant/heatmaps/{symbol}   seasonality / volatility / distribution / correlation heatmaps
  GET /quant/regime/{symbol}     risk & regime: GARCH, Hurst, GMM regime, MC cone, VaR, tests, beta, drawdowns
  GET /quant/portfolio/{symbol}  min-var / max-Sharpe / risk-parity / HRP basket + efficient frontier
  GET /quant/forecast/{symbol}   OpenBB-style statistical forecasting baselines with backtest error

All use the full daily history (period="max") where relevant, are cached per
symbol for 15 minutes, and return JSON with no NaN/Inf.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.api.routes import market_service
from app.services import universe
from app.services.quant_common import BENCH_NAMES, cached, market_benchmark

logger = logging.getLogger(__name__)
router = APIRouter()


def _history(symbol: str, period: str = "max") -> pd.DataFrame:
    df = market_service.fetch_historical_data(symbol, period=period, interval="1d")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No market data for {symbol}")
    return df


def _closes(symbols, period: str) -> Dict[str, pd.Series]:
    """Fetch several closes in parallel; failures are skipped (logged)."""
    def one(s):
        try:
            d = market_service.fetch_historical_data(s, period=period, interval="1d")
            if d is not None and not d.empty and len(d) > 120:
                return s, d["Close"]
        except Exception as e:  # pragma: no cover - network dependent
            logger.warning(f"benchmark {s} unavailable: {e}")
        return s, None
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(one, symbols))
    return {s: c for s, c in res if c is not None}


def _run(kind: str, symbol: str, fn: Callable[[], Dict]) -> Dict:
    try:
        out = cached(kind, symbol, fn)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"quant {kind} failed for {symbol}")
        raise HTTPException(status_code=500, detail=f"{kind} analytics failed: {e}")
    if not out.get("success"):
        raise HTTPException(status_code=400, detail=out.get("error", "insufficient data"))
    return out


@router.get("/quant/signals/{symbol}")
def quant_signals(symbol: str):
    """Signal board: 24 classic rules (je-suis-tm, howtrader, OpenBB ta) with full-history backtests."""
    from app.services.quant_signals import build_signals
    return _run("signals", symbol, lambda: build_signals(_history(symbol), symbol))


@router.get("/quant/heatmaps/{symbol}")
def quant_heatmaps(symbol: str):
    """Monthly, weekday×month, volatility, distribution-by-year and cross-asset correlation heatmaps."""
    from app.services.quant_heatmaps import build_heatmaps

    def go():
        df = _history(symbol)
        bench = _closes([b for b in BENCH_NAMES if b != symbol], "5y")
        return build_heatmaps(df, symbol, bench)
    return _run("heatmaps", symbol, go)


@router.get("/quant/regime/{symbol}")
def quant_regime(symbol: str):
    """Risk & regime pack."""
    from app.services.quant_regime import build_regime

    def go():
        df = _history(symbol)
        bsym = market_benchmark(symbol, (universe.get(symbol) or {}).get("market"))
        b = _closes([bsym], "10y").get(bsym)
        return build_regime(df, symbol, b, bsym)
    return _run("regime", symbol, go)


@router.get("/quant/portfolio/{symbol}")
def quant_portfolio(symbol: str):
    """Basket optimisation around the symbol (Riskfolio / ffn / pynance style)."""
    from app.services.quant_portfolio import build_portfolio, pick_basket

    def go():
        basket = pick_basket(symbol)
        closes = _closes(basket, "5y")
        if symbol not in closes:
            raise HTTPException(status_code=404, detail=f"No market data for {symbol}")
        return build_portfolio(symbol, closes)
    return _run("portfolio", symbol, go)


@router.get("/quant/forecast/{symbol}")
def quant_forecast(symbol: str):
    """Naive / drift / SES / Holt / ARIMA / Theta baselines with rolling-origin backtest."""
    from app.services.quant_forecast import build_forecast
    return _run("forecast", symbol, lambda: build_forecast(_history(symbol), symbol))
