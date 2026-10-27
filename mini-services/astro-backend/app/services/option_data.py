"""
Option chain data service
=========================
Serves option chains for the Options Lab with two sources:

1. LIVE   - Yahoo Finance (yfinance) option_chain() with TTL cache,
             per-row BSM greeks computed at the quoted implied vol.
2. MODEL  - synthetic chain: ATM vol = annualised HV20 of the underlying
             (plus a vol floor), skew shaped with Hagan SABR (beta=1,
             rho=-0.65, nu=0.9) so put wings smile up like real markets.
             Rows are BSM-priced and flagged  source="synthetic".

The strategy engine consumes the same row schema from either source, so the
lab is always functional even when Yahoo blocks chains for a symbol.
Educational use only.
"""
from app.core.ssl_fix import ensure_ssl_certs  # noqa: F401  (must run first)

import logging
import math
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.services import quant_models as qm
from app.services.market_data import MarketDataService
from app.services.universe import currency_of

logger = logging.getLogger(__name__)

RISK_FREE = 0.042          # flat term structure approximation (documented)
VOL_FLOOR = 0.12           # synthetic ATM vol floor (cash indices sit low)
CHAIN_TTL = 10 * 60        # 10 minutes
EXPIRY_TTL = 30 * 60       # 30 minutes
MAX_EXPIRIES = 16


def _nice_step(price: float) -> float:
    """Round strike step like real exchanges."""
    if price < 25:
        return 0.5
    if price < 60:
        return 1.0
    if price < 150:
        return 2.5
    if price < 400:
        return 5.0
    if price < 1000:
        return 10.0
    if price < 4000:
        return 25.0
    if price < 15000:
        return 50.0
    return 100.0


class OptionDataService:
    def __init__(self, market_service: MarketDataService):
        self.market = market_service
        self._chain_cache: Dict[str, Tuple[dict, float]] = {}
        self._exp_cache: Dict[str, Tuple[List[str], float]] = {}
        self._iv_cache: Dict[str, Tuple[float, float]] = {}   # symbol -> (atm_vol, ts)

    # ------------------------------------------------------------------
    # spot & baseline vol
    # ------------------------------------------------------------------
    def spot_of(self, symbol: str) -> Optional[float]:
        px = self.market.get_real_time_price(symbol)
        if px and px > 0:
            return float(px)
        hist = self.market.fetch_historical_data(symbol, period="5d", interval="1d")
        if hist is not None and not hist.empty:
            closes = hist["Close"].dropna()
            if len(closes):
                return float(closes.iloc[-1])
        return None

    def atm_vol_of(self, symbol: str) -> float:
        """Annualised HV20 as the ATM vol baseline (cached 1 h)."""
        hit = self._iv_cache.get(symbol)
        if hit and (time.time() - hit[1]) < 3600:
            return hit[0]
        vol = VOL_FLOOR
        try:
            hist = self.market.fetch_historical_data(symbol, period="6mo", interval="1d")
            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                if len(closes) > 30:
                    logret = np.log(closes / closes.shift(1)).dropna()
                    hv = float(logret.tail(20).std(ddof=1) * math.sqrt(252))
                    if math.isfinite(hv) and hv > 0.02:
                        vol = max(VOL_FLOOR, hv)
        except Exception as exc:
            logger.warning("atm_vol_of %s: %s", symbol, exc)
        self._iv_cache[symbol] = (vol, time.time())
        return vol

    # ------------------------------------------------------------------
    # expirations
    # ------------------------------------------------------------------
    def expirations(self, symbol: str) -> dict:
        hit = self._exp_cache.get(symbol)
        if hit and (time.time() - hit[1]) < EXPIRY_TTL:
            exps, spot = hit[0], self.spot_of(symbol)
            return self._expiry_payload(symbol, exps, spot)

        spot = self.spot_of(symbol)
        exps: List[str] = []
        try:
            import yfinance as yf
            raw = yf.Ticker(symbol).options  # type: ignore[attr-defined]
            exps = [str(e) for e in raw][:MAX_EXPIRIES]
        except Exception as exc:
            logger.warning("yfinance expirations failed for %s: %s", symbol, exc)

        if not exps:
            exps = self._weekly_fridays(spot is not None)
        self._exp_cache[symbol] = (exps, time.time())
        return self._expiry_payload(symbol, exps, spot)

    @staticmethod
    def _weekly_fridays(n: int = 12) -> List[str]:
        """Next n Fridays (weekly listed style) as ISO dates."""
        out, d = [], datetime.utcnow().date()
        while len(out) < n:
            d += timedelta(days=1)
            if d.weekday() == 4:
                out.append(d.isoformat())
        return out

    def _expiry_payload(self, symbol: str, exps: List[str], spot: Optional[float]) -> dict:
        dte = []
        for e in exps:
            try:
                days = max(0, (datetime.strptime(e, "%Y-%m-%d") - datetime.utcnow()).total_seconds() / 86400)
                dte.append(round(days, 1))
            except Exception:
                dte.append(None)
        return {
            "success": True,
            "symbol": symbol,
            "spot": spot,
            "currency": currency_of(symbol),
            "atm_vol": self.atm_vol_of(symbol) if spot else None,
            "expirations": exps,
            "dte": dte,
            "risk_free": RISK_FREE,
        }

    # ------------------------------------------------------------------
    # chain
    # ------------------------------------------------------------------
    def chain(self, symbol: str, expiry: str) -> dict:
        key = f"{symbol}|{expiry}"
        hit = self._chain_cache.get(key)
        if hit and (time.time() - hit[1]) < CHAIN_TTL:
            payload = hit[0]
            payload["spot"] = self.spot_of(symbol) or payload["spot"]
            return payload

        spot = self.spot_of(symbol)
        if not spot:
            raise ValueError(f"No spot price for {symbol}")

        calls, puts, source = None, None, "synthetic"
        try:
            import yfinance as yf
            oc = yf.Ticker(symbol).option_chain(expiry)  # type: ignore[attr-defined]
            calls, puts = oc.calls.copy(), oc.puts.copy()
            source = "live"
        except Exception as exc:
            logger.warning("chain live fetch failed %s@%s: %s", symbol, expiry, exc)

        payload = self._build_rows(symbol, expiry, spot, calls, puts, source)
        self._chain_cache[key] = (payload, time.time())
        return payload

    # ------------------------------------------------------------------
    def _build_rows(self, symbol: str, expiry: str, spot: float,
                    calls_df, puts_df, source: str) -> dict:
        T, r = self._T(expiry), RISK_FREE
        atm_vol = self.atm_vol_of(symbol)
        q = self._div_yield(symbol)
        live_ok = source == "live" and calls_df is not None and puts_df is not None \
            and len(calls_df) > 2 and len(puts_df) > 2

        if live_ok:
            strikes = sorted(set(
                [float(s) for s in calls_df["strike"].tolist()] +
                [float(s) for s in puts_df["strike"].tolist()]))
            call_by_k = {float(row["strike"]): row for _, row in calls_df.iterrows()}
            put_by_k = {float(row["strike"]): row for _, row in puts_df.iterrows()}
        else:
            source = "synthetic"
            step = _nice_step(spot)
            lo = max(step, round((spot * 0.80) / step) * step)
            hi = round((spot * 1.20) / step) * step
            strikes = list(np.arange(lo, hi + step * 0.51, step))
            strikes = [round(float(k), 2) for k in strikes]
            call_by_k, put_by_k = {}, {}

        def row_iv(iv_val: Optional[float], K: float, cp: str) -> float:
            """Quoted IV if sane, else SABR-skewed synthetic smile."""
            if iv_val and 0.02 < float(iv_val) < 3.0:
                return float(iv_val)
            return self._smile_iv(spot, K, T, atm_vol)

        def mid_of(row, model_price: float) -> Tuple[float, float]:
            bid = float(row.get("bid", 0) or 0)
            ask = float(row.get("ask", 0) or 0)
            last = float(row.get("lastPrice", 0) or 0)
            if bid > 0 and ask >= bid:
                return (bid + ask) / 2.0, (bid, ask)
            if last > 0:
                return last, (last, last)
            return model_price, (model_price, model_price)

        def _int_or0(v) -> int:
            try:
                f = float(v)
                return int(f) if math.isfinite(f) else 0
            except (TypeError, ValueError):
                return 0

        rows = []
        for K in strikes:
            entry: Dict = {"strike": round(float(K), 2)}
            for cp, by_k in (("call", call_by_k), ("put", put_by_k)):
                raw = by_k.get(K)
                if raw is not None:
                    iv = row_iv(raw.get("impliedVolatility"), K, cp)
                    g = qm.bs_price_greeks(spot, K, T, r, iv, cp, q)
                    mid, (bid, ask) = mid_of(raw, g["price"])
                    vol = _int_or0(raw.get("volume", 0))
                    oi = _int_or0(raw.get("openInterest", 0))
                    tradable = (bid > 0) or (vol > 0) or (oi > 0)
                else:
                    iv = self._smile_iv(spot, K, T, atm_vol)
                    g = qm.bs_price_greeks(spot, K, T, r, iv, cp, q)
                    mid = bid = ask = g["price"]
                    vol = oi = 0
                    tradable = False
                entry[cp] = {
                    "mid": round(mid, 4), "bid": round(bid, 4), "ask": round(ask, 4),
                    "iv": round(iv, 4), "delta": g["delta"], "gamma": g["gamma"],
                    "theta": g["theta"], "vega": g["vega"],
                    "volume": vol, "open_interest": oi,
                    "tradable": bool(tradable) if raw is not None else False,
                    "quoted": raw is not None,
                }
            entry["moneyness"] = round(K / spot, 4)
            rows.append(entry)

        return {
            "success": True,
            "symbol": symbol,
            "expiry": expiry,
            "dte": round(T * 365, 1),
            "spot": spot,
            "currency": currency_of(symbol),
            "atm_vol": round(atm_vol, 4),
            "div_yield": round(q, 4),
            "risk_free": r,
            "source": source,
            "rows": rows,
            "disclaimer": ("Live Yahoo chain; greeks are BSM at quoted IV."
                           if source == "live" else
                           "No live chain available — synthetic SABR-skewed chain "
                           "modelled from HV20. Educational use only."),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _T(expiry: str) -> float:
        try:
            exp_dt = datetime.strptime(expiry, "%Y-%m-%d").replace(hour=21)
        except Exception:
            exp_dt = datetime.utcnow() + timedelta(days=30)
        days = (exp_dt - datetime.utcnow()).total_seconds() / 86400
        return max(days, 0.5) / 365.0

    def _div_yield(self, symbol: str) -> float:
        """Dividend yield proxy from cached info (0 default)."""
        try:
            info = self.market.get_symbol_info(symbol)
            dy = info.get("dividend_yield") if isinstance(info, dict) else None
            if dy and 0 < float(dy) < 0.2:
                return float(dy)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _smile_iv(spot: float, K: float, T: float, atm_vol: float) -> float:
        """Hagan SABR smile (beta=1, rho=-0.65, nu=0.9) around HV-derived ATM."""
        alpha = atm_vol
        v = qm.sabr_vol(spot, K, max(T, 1 / 365), alpha, beta=1.0, rho=-0.65, nu=0.9)
        if not math.isfinite(v) or v <= 0.02:
            v = atm_vol
        return min(max(v, 0.03), 3.0)
