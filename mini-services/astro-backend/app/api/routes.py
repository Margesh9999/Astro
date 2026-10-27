"""
API routes for AstroTrader
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import swisseph as swe

from app.services.predictor import PredictorService
from app.services.market_data import MarketDataService
from app.core.config import settings
from app.core.vedic import VedicCalculator

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
predictor_service = PredictorService(
    ephe_path=settings.ASTRO_EPHE_PATH,
    cache_dir=settings.ASTRO_CACHE_DIR,
    use_vedic=False  # Can be made configurable
)

market_service = MarketDataService(cache_dir=settings.ASTRO_CACHE_DIR)

vedic_calculator = VedicCalculator(ayanamsa_mode=swe.SIDM_LAHIRI)

SUPPORTED_SYMBOLS = [
    {"symbol": "^GSPC", "name": "S&P 500", "market": "US", "flag": "🇺🇸"},
    {"symbol": "^IXIC", "name": "NASDAQ Composite", "market": "US", "flag": "🇺🇸"},
    {"symbol": "^NSEI", "name": "Nifty 50", "market": "India", "flag": "🇮🇳"},
    {"symbol": "^BSESN", "name": "BSE Sensex", "market": "India", "flag": "🇮🇳"},
    {"symbol": "^FTSE", "name": "FTSE 100", "market": "UK", "flag": "🇬🇧"},
]

# Pydantic models for request/response
class TrainRequest(BaseModel):
    symbol: str = "^GSPC"
    lookback_years: int = 5
    use_vedic: bool = False

class PredictRequest(BaseModel):
    symbol: str = "^GSPC"
    days_ahead: int = 30
    use_vedic: bool = False

class BacktestRequest(BaseModel):
    symbol: str = "^GSPC"
    lookback_years: int = 6
    use_vedic: bool = False
    test_fraction: float = 0.25

class TrainResponse(BaseModel):
    success: bool
    symbol: str
    samples: int
    date_range: str
    linear_r2: float
    rf_r2: float
    feature_importance: Dict[str, float]
    error: Optional[str] = None

class PredictResponse(BaseModel):
    success: bool
    symbol: str
    current_price: float
    prediction_days: int
    dates: List[str]
    daily_returns: List[float]
    cumulative_returns: List[float]
    projected_prices: List[float]
    model_used: str
    vedic: bool
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="AstroTrader API",
        version="0.1.0"
    )


@router.get("/symbols")
async def get_symbols():
    """List supported market symbols"""
    return {"symbols": SUPPORTED_SYMBOLS}


@router.post("/train", response_model=TrainResponse)
async def train_model(request: TrainRequest):
    """Train the prediction model"""
    try:
        logger.info(f"Training request received for {request.symbol} (vedic={request.use_vedic})")

        global predictor_service
        if request.use_vedic != predictor_service.use_vedic:
            predictor_service = PredictorService(
                ephe_path=settings.ASTRO_EPHE_PATH,
                cache_dir=settings.ASTRO_CACHE_DIR,
                use_vedic=request.use_vedic
            )

        result = predictor_service.train_model(
            symbol=request.symbol,
            lookback_years=request.lookback_years
        )

        if result['success']:
            return TrainResponse(
                success=True,
                symbol=result['symbol'],
                samples=result['samples'],
                date_range=result['date_range'],
                linear_r2=result['linear_r2'],
                rf_r2=result['rf_r2'],
                feature_importance=result['feature_importance']
            )
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Training failed'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in train endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict", response_model=PredictResponse)
async def predict_market(request: PredictRequest):
    """Generate market predictions"""
    try:
        logger.info(f"Prediction request received for {request.symbol}")

        global predictor_service
        if request.use_vedic != predictor_service.use_vedic:
            predictor_service = PredictorService(
                ephe_path=settings.ASTRO_EPHE_PATH,
                cache_dir=settings.ASTRO_CACHE_DIR,
                use_vedic=request.use_vedic
            )

        result = predictor_service.predict_future(
            symbol=request.symbol,
            days_ahead=request.days_ahead
        )

        if result['success']:
            return PredictResponse(
                success=True,
                symbol=result['symbol'],
                current_price=result['current_price'],
                prediction_days=result['prediction_days'],
                dates=result['dates'],
                daily_returns=result['daily_returns'],
                cumulative_returns=result['cumulative_returns'],
                projected_prices=result['projected_prices'],
                model_used=result['model_used'],
                vedic=result['vedic']
            )
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Prediction failed'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in predict endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/{symbol}")
async def get_feature_importance(symbol: str = "^GSPC"):
    """Get feature importance for a symbol"""
    try:
        logger.info(f"Feature importance request for {symbol}")
        if not predictor_service.is_trained or getattr(predictor_service, 'last_trained_symbol', None) != symbol:
            result = predictor_service.train_model(symbol=symbol)
            if not result.get('success'):
                raise HTTPException(status_code=400, detail=result.get('error', 'Training failed'))

        features = predictor_service.get_feature_importance()
        return {
            "symbol": symbol,
            "features": [{"name": name, "importance": float(imp)} for name, imp in features]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feature importance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/planetary/{date}")
async def get_planetary_positions(date: str, vedic: bool = False):
    """Get planetary positions for a specific date (YYYY-MM-DD)"""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        julian_day = swe.julday(target_date.year, target_date.month, target_date.day, 0.0)

        if vedic:
            positions = vedic_calculator.calculate_all_planets_vedic(julian_day)
            # Add Rahu/Ketu (mean node) for the Vedic view
            for node_name, node_id in (("Rahu", swe.MEAN_NODE),):
                try:
                    positions[node_name] = vedic_calculator.calculate_planet_position_vedic(node_id, julian_day)
                    ketu_lon = (positions[node_name]["longitude"] + 180) % 360
                    ketu = dict(positions[node_name])
                    ketu["longitude"] = ketu_lon
                    ketu["sign_number"] = int(ketu_lon // 30)
                    ketu["degree_within_sign"] = ketu_lon % 30
                    ketu["sign"] = vedic_calculator.calculate_planet_position_vedic(node_id, julian_day)["sign"]  # placeholder, fixed below
                    nak = vedic_calculator.calculate_nakshatra(ketu_lon)
                    ketu["nakshatra"] = nak["nakshatra"]
                    ketu["nakshatra_index"] = nak["nakshatra_index"]
                    ketu["pada"] = nak["pada"]
                    ketu["is_retrograde"] = True
                    positions["Ketu"] = ketu
                    # fix sign name for Ketu
                    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
                    positions["Ketu"]["sign"] = signs[ketu["sign_number"]]
                except Exception as e:
                    logger.warning(f"Could not compute nodes: {e}")
        else:
            positions = predictor_service.ephemeris.calculate_all_planets(julian_day)

        # Vedic mode: add the Ascendant (Lagna) for the day so the frontend can
        # draw a proper North Indian kundali. Reference: local noon IST over
        # Ujjain (23.1793 N, 75.7849 E) — the traditional zero-meridian of
        # Hindu astronomy (the "Lanka line").
        if vedic:
            try:
                signs_list = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                              "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
                swe.set_sid_mode(swe.SIDM_LAHIRI)
                # 12:00 IST = 06:30 UT
                jd_noon = swe.julday(target_date.year, target_date.month, target_date.day, 6.5)
                cusps, ascmc = swe.houses_ex(
                    jd_noon, 23.1793, 75.7849, b'W', flags=swe.FLG_SIDEREAL
                )
                asc_lon = ascmc[0] % 360
                asc_nak = vedic_calculator.calculate_nakshatra(asc_lon)
                positions["Lagna"] = {
                    "longitude": asc_lon,
                    "sign": signs_list[int(asc_lon // 30)],
                    "sign_number": int(asc_lon // 30),
                    "degree_within_sign": asc_lon % 30,
                    "is_retrograde": False,
                    "nakshatra": asc_nak["nakshatra"],
                    "nakshatra_index": asc_nak["nakshatra_index"],
                    "pada": asc_nak["pada"],
                }
                # Whole-sign houses counted from the Lagna sign
                lagna_sign = int(asc_lon // 30)
                for gname, p in positions.items():
                    sign_num = p.get("sign_number", int(p["longitude"] // 30))
                    p["house"] = (sign_num - lagna_sign) % 12 + 1
                    deg = p.get("degree_within_sign", p["longitude"] % 30)
                    dig, dig_score = _dignity(gname, sign_num, deg)
                    p["dignity"] = dig
                    p["dignity_score"] = _f(dig_score)
            except Exception as e:
                logger.warning(f"Could not compute day ascendant: {e}")

        aspects = predictor_service.aspects_calculator.calculate_all_aspects(positions)

        return {
            "date": date,
            "julian_day": julian_day,
            "ayanamsa": vedic_calculator.get_ayanamsa(julian_day) if vedic else None,
            "vedic": vedic,
            "planetary_positions": positions,
            "aspects": aspects
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error getting planetary positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _f(x, default=0.0):
    """NaN/inf-safe float coercion (NaN is illegal in FastAPI JSON responses)."""
    try:
        v = float(x)
        return default if (np.isnan(v) or np.isinf(v)) else v
    except (TypeError, ValueError):
        return default


@router.get("/market/{symbol}")
async def get_market_quote(symbol: str):
    """Get real-time market quote for a symbol via yfinance"""
    try:
        hist = market_service.fetch_historical_data(symbol, period="5d", interval="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No market data for {symbol}")

        hist = hist[hist['Close'].notna()]
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No market data for {symbol}")

        last_close = _f(hist['Close'].iloc[-1])
        prev_close = _f(hist['Close'].iloc[-2], last_close) if len(hist) > 1 else last_close
        change = last_close - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        price_now = market_service.get_real_time_price(symbol) or last_close

        info = market_service.get_symbol_info(symbol)

        # Recent history for sparkline (30 sessions)
        hist30 = market_service.fetch_historical_data(symbol, period="1mo", interval="1d")
        spark = []
        if not hist30.empty:
            for idx, row in hist30.iterrows():
                if pd.isna(row['Close']):
                    continue  # skip partial rows in the sparkline
                dt = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else pd_to_dt(idx)
                spark.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "close": _f(row['Close']),
                    "volume": _f(row['Volume']),
                })

        last_row = hist.iloc[-1]
        return {
            "symbol": symbol,
            "name": info.get('name', symbol),
            "currency": info.get('currency', 'USD'),
            "price": _f(price_now, last_close),
            "previous_close": prev_close,
            "change": change,
            "change_percent": change_pct,
            "day_high": _f(last_row['High'], last_close),
            "day_low": _f(last_row['Low'], last_close),
            "open": _f(last_row['Open'], last_close),
            "volume": _f(last_row['Volume']),
            "timestamp": datetime.now().isoformat(),
            "sparkline": spark,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting market quote for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def pd_to_dt(idx):
    from pandas import Timestamp
    if isinstance(idx, Timestamp):
        return idx.to_pydatetime()
    return datetime.now()


@router.post("/backtest")
async def backtest_strategy(request: BacktestRequest):
    """
    Walk-forward backtest: train astro models on the first (1 - test_fraction)
    of history, then trade the remaining sessions using predicted direction.
    Compares astro strategy vs buy & hold.
    """
    try:
        global predictor_service
        if request.use_vedic != predictor_service.use_vedic:
            predictor_service = PredictorService(
                ephe_path=settings.ASTRO_EPHE_PATH,
                cache_dir=settings.ASTRO_CACHE_DIR,
                use_vedic=request.use_vedic
            )

        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(request.lookback_years * 365.25))

        market_df = predictor_service.market_data.fetch_historical_data(
            request.symbol, period=f"{(end_date - start_date).days}d", interval="1d"
        )
        if market_df.empty or len(market_df) < 100:
            raise HTTPException(status_code=400, detail="Not enough market data for backtest")

        # Build aligned features per trading day
        dates, returns, feats = [], [], []
        for date_idx, row in market_df.iterrows():
            dt = date_idx.to_pydatetime() if hasattr(date_idx, 'to_pydatetime') else date_idx
            dt = dt.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
            if not (start_date <= dt <= end_date):
                continue
            jd = predictor_service.ephemeris.date_to_julian(dt)
            if predictor_service.use_vedic and predictor_service.vedic_calculator is not None:
                pos = predictor_service.vedic_calculator.calculate_all_planets_vedic(jd)
            else:
                pos = predictor_service.ephemeris.calculate_all_planets(jd)
            asp = predictor_service.aspects_calculator.calculate_all_aspects(pos)
            ts = {**pos,
                  'aspect_score_conjunction': predictor_service.aspects_calculator.get_aspect_score(asp, 'conjunction'),
                  'aspect_score_opposition': predictor_service.aspects_calculator.get_aspect_score(asp, 'opposition'),
                  'aspect_score_trine': predictor_service.aspects_calculator.get_aspect_score(asp, 'trine'),
                  'aspect_score_square': predictor_service.aspects_calculator.get_aspect_score(asp, 'square'),
                  'aspect_score_sextile': predictor_service.aspects_calculator.get_aspect_score(asp, 'sextile')}
            dates.append(dt)
            returns.append(0.0 if pd.isna(row['Returns']) else float(row['Returns']))
            feats.append(ts)

        X, feature_names = predictor_service.correlation_engine.prepare_planetary_features(
            feats, include_aspects=False, vedic=request.use_vedic)
        y = np.array(returns)

        n = len(y)
        split = int(n * (1 - request.test_fraction))
        if n - split < 20:
            raise HTTPException(status_code=400, detail="Test window too small")

        # Train on train window only
        predictor_service.correlation_engine.train_models(X[:split], y[:split])

        # Walk forward on test window
        preds = predictor_service.correlation_engine.predict_returns(X[split:], 'random_forest')
        test_dates = [d.strftime("%Y-%m-%d") for d in dates[split:]]
        test_returns = y[split:]

        # Strategy: long when predicted return > 0, else flat (cash)
        strat_returns = np.where(preds > 0, test_returns, 0.0)

        def equity_curve(r):
            return np.cumprod(1 + r)

        eq_strat = equity_curve(strat_returns)
        eq_bh = equity_curve(test_returns)

        def metrics(r, eq):
            total = float(eq[-1] - 1) * 100
            years = len(r) / 252.0
            annual = float((eq[-1]) ** (1 / max(years, 1e-9)) - 1) * 100
            sharpe = float(np.mean(r) / (np.std(r) + 1e-12) * np.sqrt(252))
            peak = np.maximum.accumulate(eq)
            dd = float(np.min(eq / peak - 1)) * 100
            active = r[r != 0]
            win = float((active > 0).sum() / max(len(active), 1)) * 100
            return total, annual, sharpe, dd, win

        s_total, s_annual, s_sharpe, s_dd, s_win = metrics(strat_returns, eq_strat)
        b_total, b_annual, b_sharpe, b_dd, _ = metrics(test_returns, eq_bh)

        # Equity curve samples (downsample to max ~120 points)
        step = max(1, len(test_dates) // 120)
        curve = [
            {
                "date": test_dates[i],
                "strategy": float(eq_strat[i] * 100),
                "buy_hold": float(eq_bh[i] * 100),
            }
            for i in range(0, len(test_dates), step)
        ]

        return {
            "success": True,
            "symbol": request.symbol,
            "vedic": request.use_vedic,
            "train_samples": int(split),
            "test_samples": int(n - split),
            "test_range": f"{test_dates[0]} to {test_dates[-1]}",
            "strategy": {
                "total_return": s_total, "annual_return": s_annual,
                "sharpe": s_sharpe, "max_drawdown": s_dd, "win_rate": s_win,
            },
            "buy_hold": {
                "total_return": b_total, "annual_return": b_annual,
                "sharpe": b_sharpe, "max_drawdown": b_dd,
            },
            "equity_curve": curve,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
async def get_astro_events(days: int = 30):
    """
    Compute real upcoming astrological events for the next `days` days:
    - Major aspects forming between planet pairs (angle crossing exact aspect)
    - New / full moons (Sun-Moon elongation crossing 0 / 180)
    - Sign ingresses (planet changing sidereal sign)
    """
    try:
        days = max(7, min(days, 90))
        events = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        major_aspects = [(0.0, "Conjunction"), (60.0, "Sextile"), (90.0, "Square"),
                         (120.0, "Trine"), (180.0, "Opposition")]

        planet_ids = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
            "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
            "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
        }
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

        def minimal_step(raw_prev: float, raw_now: float) -> float:
            """Signed minimal angular step between two raw (0..360) positions."""
            delta = raw_now - raw_prev
            if delta > 180:
                delta -= 360
            elif delta < -180:
                delta += 360
            return delta

        prev_pos: Optional[Dict[str, float]] = None
        # continuous (unwrapped) relative coordinate per planet pair
        pair_cont: Dict[Tuple[str, str], float] = {}

        for d in range(days + 1):
            day = today + timedelta(days=d)
            jd = swe.julday(day.year, day.month, day.day, 0.0)
            pos: Dict[str, float] = {}
            for name, pid in planet_ids.items():
                lon = swe.calc_ut(jd, pid)[0][0]
                pos[name] = lon
                if prev_pos is not None and name in prev_pos:
                    old_sign = int(prev_pos[name] // 30)
                    new_sign = int(lon // 30)
                    if old_sign != new_sign:
                        events.append({
                            "date": day.strftime("%Y-%m-%d"),
                            "event": f"{name} enters {signs[new_sign]}",
                            "type": "ingress",
                            "planets": [name],
                            "significance": "Medium",
                            "description": f"{name} transits from {signs[old_sign]} into {signs[new_sign]}."
                        })

            if prev_pos is not None:
                names = list(pos.keys())
                for i, p1 in enumerate(names):
                    for p2 in names[i + 1:]:
                        key = (p1, p2)
                        raw_now = (pos[p1] - pos[p2]) % 360
                        raw_prev = (prev_pos[p1] - prev_pos[p2]) % 360
                        cont = pair_cont.get(key, raw_prev) + minimal_step(raw_prev, raw_now)
                        pair_cont[key] = cont

                        for angle, label in major_aspects:
                            # check unwrapped targets around the continuous coordinate
                            center = 360.0 * round(cont / 360.0)
                            for k in (-1, 0, 1):
                                target = center + angle + 360 * k
                                # crossing between pair_cont_prev and cont
                                prev_cont = cont - minimal_step(raw_prev, raw_now)
                                if (prev_cont - target) * (cont - target) < 0:
                                    if p1 == "Sun" and p2 == "Moon":
                                        if angle == 0.0:
                                            ev, sig, desc = "New Moon", "High", "Sun-Moon conjunction — lunar reset, new beginnings."
                                        else:
                                            ev, sig, desc = "Full Moon", "High", "Sun-Moon opposition — culmination and release."
                                    else:
                                        ev, sig, desc = f"{p1} {label} {p2}", (
                                            "High" if angle in (0.0, 120.0, 180.0) else "Medium"
                                        ), f"Exact {label.lower()} between {p1} and {p2} ({int(angle)}°)."
                                    events.append({
                                        "date": day.strftime("%Y-%m-%d"),
                                        "event": ev,
                                        "type": "lunar_phase" if p1 == "Sun" and p2 == "Moon" else label.lower(),
                                        "planets": [p1, p2],
                                        "significance": sig,
                                        "description": desc,
                                    })
                                    break

            prev_pos = pos

        # de-dup (same date+event), sort by date
        seen = set()
        unique = []
        for e in events:
            key = (e["date"], e["event"])
            if key not in seen:
                seen.add(key)
                unique.append(e)
        unique.sort(key=lambda e: e["date"])
        return {"success": True, "events": unique, "count": len(unique)}
    except Exception as e:
        logger.error(f"Error computing astro events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/natal")
async def get_natal_chart():
    """
    Vedic (sidereal, Lahiri) birth chart for the native:
    born 23 April 1994, 06:45 IST (01:15 UTC), Vallabh Vidyanagar, Gujarat, India
    (22.5347 N, 73.13 E). Returns the nine grahas + Lagna with nakshatra/pada.
    """
    try:
        # 06:45 IST = 01:15 UTC
        jd = swe.julday(1994, 4, 23, 1.25)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        ayanamsa = swe.get_ayanamsa_ut(jd)

        grahas = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
            "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
            "Rahu": swe.MEAN_NODE,
        }
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

        positions = {}
        for name, pid in grahas.items():
            data = vedic_calculator.calculate_planet_position_vedic(pid, jd)
            if name == "Rahu":
                positions[name] = data
                # Ketu is always 180° opposite Rahu
                ketu_lon = (data["longitude"] + 180) % 360
                nak = vedic_calculator.calculate_nakshatra(ketu_lon)
                positions["Ketu"] = {
                    "longitude": ketu_lon,
                    "sign": signs[int(ketu_lon // 30)],
                    "sign_number": int(ketu_lon // 30),
                    "degree_within_sign": ketu_lon % 30,
                    "is_retrograde": True,
                    "nakshatra": nak["nakshatra"],
                    "nakshatra_index": nak["nakshatra_index"],
                    "pada": nak["pada"],
                }
            else:
                positions[name] = data

        # Ascendant (sidereal) — Vallabh Vidyanagar
        cusps, ascmc = swe.houses_ex(jd, 22.5347, 73.13, b'W', flags=swe.FLG_SIDEREAL)
        asc_lon = ascmc[0] % 360
        asc_nak = vedic_calculator.calculate_nakshatra(asc_lon)
        positions["Lagna"] = {
            "longitude": asc_lon,
            "sign": signs[int(asc_lon // 30)],
            "sign_number": int(asc_lon // 30),
            "degree_within_sign": asc_lon % 30,
            "is_retrograde": False,
            "nakshatra": asc_nak["nakshatra"],
            "nakshatra_index": asc_nak["nakshatra_index"],
            "pada": asc_nak["pada"],
        }

        # Whole-sign house: count from Lagna sign
        lagna_sign = int(asc_lon // 30)
        for gname, p in positions.items():
            sign_num = p.get("sign_number", int(p["longitude"] // 30))
            p["house"] = (sign_num - lagna_sign) % 12 + 1
            deg = p.get("degree_within_sign", p["longitude"] % 30)
            dig, dig_score = _dignity(gname, sign_num, deg)
            p["dignity"] = dig
            p["dignity_score"] = _f(dig_score)

        return {
            "success": True,
            "native": "Margesh",
            "birth": "1994-04-23 06:45 IST, Vallabh Vidyanagar, Gujarat, India",
            "ayanamsa": ayanamsa,
            "ayanamsa_mode": "Lahiri (Chitrapaksha)",
            "positions": positions,
        }
    except Exception as e:
        logger.error(f"Error computing natal chart: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Suri-inspired Astro-Signal endpoints
# =============================================================================
from app.services.suri import SuriSignalEngine  # noqa: E402

suri_engine = SuriSignalEngine(ephe_path=settings.ASTRO_EPHE_PATH)


@router.get("/astro-signal/{symbol}")
async def get_astro_signal(symbol: str):
    """Suri-style composite: mood, reversal/vol scores, timing windows, 5-day range."""
    try:
        today = datetime.utcnow().date().strftime("%Y-%m-%d")
        hist = market_service.fetch_historical_data(symbol, period="1y", interval="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No market data for {symbol}")

        closes = [float(c) for c in hist['Close'].dropna().tolist()]
        dates = [idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                 for idx in hist.dropna(subset=['Close']).index]
        spot = closes[-1]

        mood = suri_engine.market_mood(today)
        rev = suri_engine.reversal_score(today)
        vol = suri_engine.volatility_score(today)
        alerts = suri_engine.timing_alerts(today, days=14)
        rng = suri_engine.five_day_range(symbol, spot, closes, horizon=5)
        comp = suri_engine.composite_signal(symbol, closes)

        return {
            "success": True,
            "symbol": symbol,
            "date": today,
            "spot": _f(spot),
            "mood": mood,
            "reversal": rev,
            "volatility": vol,
            "timing_alerts": alerts,
            "five_day_range": rng,
            "composite": comp,
            "inspired_by": "Mohnish Suri (AstralAlgo) concepts - educational reimplementation",
            "disclaimer": "Educational exploration only - no proven predictive value.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"astro-signal error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Institutional quant endpoints (ffn / gs-quant / vollib / pysabr / TFF inspired)
# =============================================================================
from app.services import quant_models as qm  # noqa: E402


def _load_returns(symbol: str, years: int = 3):
    period = f"{max(1, min(10, years))}y"
    hist = market_service.fetch_historical_data(symbol, period=period, interval="1d")
    if hist.empty:
        raise HTTPException(status_code=404, detail=f"No market data for {symbol}")
    hist = hist.dropna(subset=['Close'])
    rets = hist['Close'].pct_change().dropna()
    dates = [idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
             for idx in rets.index]
    return dates, rets.values


@router.get("/quant/stats/{symbol}")
async def get_quant_stats(symbol: str, years: int = 3):
    """ffn-style performance analytics + drawdown + monthly table."""
    try:
        dates, rets = _load_returns(symbol, years)
        stats = qm.performance_stats(rets)
        dd = qm.drawdown_series(dates, rets)
        monthly = qm.monthly_returns(dates, rets)
        return {"success": True, "symbol": symbol, "stats": stats,
                "drawdown": dd, "monthly": monthly,
                "observations": int(len(rets))}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"quant stats error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quant/risk/{symbol}")
async def get_quant_risk(symbol: str, years: int = 3, conf: float = 0.95,
                         position: float = 1_000_000.0):
    """gs-quant-style VaR / expected shortfall."""
    try:
        _, rets = _load_returns(symbol, years)
        return {"success": True, "symbol": symbol,
                "risk": qm.var_cvar(rets, conf=conf, position_value=position)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"quant risk error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class OptionsPriceRequest(BaseModel):
    model: str = "bs"          # bs | black76 | crr | asian | mc | heston
    cp: str = "call"           # call | put
    S: float                   # spot (or forward for black76)
    K: float
    T: float = 0.1             # years
    r: float = 0.04
    q: float = 0.0
    sigma: float = 0.18
    american: bool = False
    steps: int = 200
    n_paths: int = 100000
    # heston params
    kappa: float = 2.0
    theta: float = 0.06
    sigma_v: float = 0.3
    rho: float = -0.7
    v0: float = 0.04


@router.post("/options/price")
async def post_options_price(req: OptionsPriceRequest):
    """Multi-model options pricing lab (vollib/optlib/Q-Fin/TFF parity)."""
    try:
        m = req.model.lower()
        if m == "bs":
            res = qm.bs_price_greeks(req.S, req.K, req.T, req.r, req.sigma, req.cp, req.q)
            res.update(model="Black-Scholes-Merton")
        elif m == "black76":
            res = qm.black76_price_greeks(req.S, req.K, req.T, req.r, req.sigma, req.cp)
            res.update(model="Black-76 (futures/forward)")
        elif m == "crr":
            res = {"price": qm.crr_binomial(req.S, req.K, req.T, req.r, req.sigma,
                                            req.cp, req.steps, req.american),
                   "model": f"CRR binomial ({'American' if req.american else 'European'}, {req.steps} steps)"}
        elif m == "asian":
            res = {"price": qm.asian_geometric(req.S, req.K, req.T, req.r, req.sigma,
                                               req.cp, req.q),
                   "model": "Asian geometric-average (closed form)"}
        elif m == "mc":
            res = qm.mc_gbm_price(req.S, req.K, req.T, req.r, req.sigma, req.cp,
                                  req.n_paths)
            res.update(model="GBM Monte-Carlo (antithetic)")
        elif m == "heston":
            price = qm.heston_call_lewis(req.S, req.K, req.T, req.r, req.q,
                                         req.kappa, req.theta, req.sigma_v,
                                         req.rho, req.v0)
            # BS-approx greeks at effective vol for intuition
            eff = qm.implied_vol(price, req.S, req.K, req.T, req.r, req.cp, req.q) or req.theta ** 0.5
            res = qm.bs_price_greeks(req.S, req.K, req.T, req.r, eff, req.cp, req.q)
            res.update(model="Heston (Lewis 2001 integral)",
                       heston_price=price, effective_vol=eff)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown model '{req.model}'")
        res["success"] = True
        res["inputs"] = {"S": req.S, "K": req.K, "T": req.T, "r": req.r,
                         "q": req.q, "sigma": req.sigma, "cp": req.cp}
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"options price error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class IVRequest(BaseModel):
    price: float
    S: float
    K: float
    T: float = 0.1
    r: float = 0.04
    q: float = 0.0
    cp: str = "call"


@router.post("/options/iv")
async def post_options_iv(req: IVRequest):
    iv = qm.implied_vol(req.price, req.S, req.K, req.T, req.r, req.cp, req.q)
    if iv is None:
        raise HTTPException(status_code=422, detail="IV not bracketed - price outside arbitrage bounds?")
    return {"success": True, "implied_vol": iv}


class SabrRequest(BaseModel):
    forward: float
    T: float = 0.25
    atm_vol: float
    beta: float = 1.0
    rho: float = -0.3
    nu: float = 0.8
    moneyness: Optional[List[float]] = None


@router.post("/options/sabr")
async def post_options_sabr(req: SabrRequest):
    try:
        smile = qm.sabr_smile(req.forward, req.T, req.atm_vol, req.beta,
                              req.rho, req.nu, req.moneyness)
        smile["success"] = True
        return smile
    except Exception as e:
        logger.error(f"sabr error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bond")
async def get_bond(face: float = 1000.0, coupon: float = 0.05, ytm: float = 0.045,
                   years: float = 10.0, freq: int = 2):
    """pyql/FinancePy-style bond analytics."""
    try:
        analytics = qm.bond_analytics(face, coupon, ytm, years, freq)
        solved_ytm = qm.bond_ytm(analytics["price"], face, coupon, years, freq)
        return {"success": True, "analytics": analytics,
                "ytm_roundtrip": solved_ytm,
                "inputs": {"face": face, "coupon": coupon, "ytm": ytm,
                           "years": years, "freq": freq}}
    except Exception as e:
        logger.error(f"bond error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Instrument universe (searchable picker: all markets x all instruments)
# =============================================================================
from app.services import universe as uni  # noqa: E402


@router.get("/universe")
async def get_universe(q: str = "", market: str = "", type: str = "",
                       options_only: bool = False, limit: int = 60):
    """Search the curated instrument universe (symbol or name, market/type filters)."""
    try:
        rows = uni.search(q=q, market=market, type_=type,
                          options_only=options_only, limit=limit)
        return {"success": True, "count": len(rows), "results": rows}
    except Exception as e:
        logger.error(f"universe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/universe/meta")
async def get_universe_meta():
    """Market/type facet counts for the picker UI."""
    return {"success": True, "meta": uni.meta()}


# =============================================================================
# Institutional Options Lab: chains, strategy engine, income planner
# =============================================================================
from app.services.option_data import OptionDataService  # noqa: E402
from app.services import option_strategies as strat  # noqa: E402
from app.services.income_planner import IncomePlanner  # noqa: E402

option_service = OptionDataService(market_service)
income_planner = IncomePlanner(option_service, market_service)


@router.get("/options/expirations/{symbol}")
async def get_option_expirations(symbol: str):
    """Listed expirations + spot + ATM vol baseline (weekly-Friday fallback)."""
    try:
        return option_service.expirations(symbol)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"expirations error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/chain/{symbol}")
async def get_option_chain(symbol: str, expiry: str):
    """Full option chain (live Yahoo when available, else synthetic SABR model)."""
    try:
        return option_service.chain(symbol, expiry)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"chain error {symbol}@{expiry}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/strategies")
async def get_option_strategies():
    """Strategy catalogue (14 institutional structures with defaults)."""
    return {"success": True, "strategies": strat.STRATEGY_CATALOG}


class StrategyRequest(BaseModel):
    symbol: str = "SPY"
    strategy: str = "iron_condor"
    expiry: Optional[str] = None
    dte_target: int = 35          # used when expiry not given
    qty: int = 1
    exit_dte: int = 21
    params: Optional[Dict[str, Any]] = None


@router.post("/options/strategy")
async def post_options_strategy(req: StrategyRequest):
    """Build + fully analyse a multi-leg strategy (legs, greeks, POP, margin,
    payoff curve, spot x IV scenario matrix)."""
    try:
        if req.strategy not in strat.CATALOG_BY_KEY:
            raise HTTPException(status_code=404, detail=f"Unknown strategy '{req.strategy}'")
        catalog = strat.CATALOG_BY_KEY[req.strategy]

        exp_res = option_service.expirations(req.symbol)
        spot = exp_res.get("spot")
        if not spot:
            raise HTTPException(status_code=404, detail=f"No spot for {req.symbol}")
        dates, dtes = exp_res["expirations"], exp_res["dte"]
        if not dates:
            raise HTTPException(status_code=404, detail=f"No expirations for {req.symbol}")

        # resolve near expiry: user-specified, else closest to dte_target
        if req.expiry:
            near_i = dates.index(req.expiry) if req.expiry in dates else 0
        else:
            near_i = min(range(len(dates)),
                         key=lambda i: abs((dtes[i] or req.dte_target) - req.dte_target))
        expiry_near = dates[near_i]
        chain_near = option_service.chain(req.symbol, expiry_near)
        spot = chain_near["spot"]

        chain_far = None
        if catalog.get("two_expiries"):
            far_i = min(near_i + 2, len(dates) - 1)
            if far_i <= near_i:
                far_i = min(near_i + 1, len(dates) - 1)
            if far_i > near_i:
                chain_far = option_service.chain(req.symbol, dates[far_i])

        qty = max(1, min(int(req.qty or 1), 1000))
        res = strat.analyze_strategy(
            req.strategy, req.symbol, spot, chain_near, chain_far,
            params=req.params, qty=qty,
            exit_dte=max(1, int(req.exit_dte or 21)))
        res["expirations_available"] = dates
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"strategy error {req.symbol}/{req.strategy}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class IncomePlanRequest(BaseModel):
    capital: float = 100000.0     # GBP
    target_weekly: float = 500.0
    focus: str = "global"         # global | uk | us | india


@router.post("/income/plan")
async def post_income_plan(req: IncomePlanRequest):
    """Weekly income planner: capital requirements per archetype + ladder of
    live example tickets + honest sustainability verdict."""
    try:
        focus = {"global": "global", "uk": "global", "us": "global",
                 "india": "India"}.get(req.focus.lower(), "global")
        return income_planner.plan(capital=req.capital,
                                   target_weekly=req.target_weekly,
                                   focus=focus)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"income plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# T1–T13 enhancement endpoints
# =============================================================================
from app.services.jataka import JatakaEngine, _dignity  # noqa: E402
from app.services.quant_analytics import build_analytics  # noqa: E402

# cross-asset correlation block in /analytics/charts — set to 0 to skip benchmark fetches
import os as _os  # noqa: E402
CORR_BENCHMARKS_ENABLED = _os.getenv("QUANT_CORR_BENCHMARKS", "1") not in ("0", "false", "False")
from app.services.agents import TradingAgentsEngine  # noqa: E402
from app.services.concepts import all_concepts  # noqa: E402

jataka_engine = JatakaEngine(ayanamsa_mode=swe.SIDM_LAHIRI)
agents_engine = TradingAgentsEngine()


@router.get("/jataka/places")
async def jataka_places(q: str = ""):
    """Search the birth-place gazetteer (T12⑤ configurable birth place)."""
    return {"success": True, "places": jataka_engine.search_places(q)}


@router.get("/jataka/report")
async def jataka_report(symbol: str = "^GSPC", name: str = "", date: str = "",
                        time: str = "", place: str = "", capital: float = 50000.0,
                        target_weekly: float = 500.0):
    """
    Full Jataka pack (T4 + T12 + T13): configurable natal chart, corrected
    Vimshottari dasha tree, strengths, market/sector/strategy recommendations,
    income forecast, lifetime wealth phases, today's transits and the final
    synthesis for the selected symbol.
    """
    try:
        sym_info = market_service.get_symbol_info(symbol)
        symbol_name = sym_info.get("name", symbol) if isinstance(sym_info, dict) else symbol
        report = jataka_engine.full_report(
            symbol=symbol, symbol_name=symbol_name, capital=capital,
            target_weekly=target_weekly, name=name, date=date, time=time, place=place)
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"jataka report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ZooTrainRequest(BaseModel):
    symbol: str = "^GSPC"
    use_vedic: bool = False
    full_history: bool = True   # T7: train from inception with the maximum data


# In-process zoo training jobs (threaded, polled via /train/zoo/status)
_ZOO_JOBS: Dict[str, Dict] = {}
_ZOO_LOCK = __import__("threading").Lock()


def _zoo_job_key(symbol: str, vedic: bool, full_history: bool) -> str:
    return f"{symbol}|{int(vedic)}|{int(full_history)}"


def _run_zoo_job(job_id: str, symbol: str, vedic: bool, full_history: bool):
    global predictor_service
    job = _ZOO_JOBS[job_id]
    try:
        job["stage"] = "collecting features"
        def _cb(stage, done, total):
            job["stage"] = stage
            job["progress"] = int(10 + 85 * done / max(1, total))
        if full_history:
            result = predictor_service.train_model_full_history(symbol, use_vedic=vedic, progress_cb=_cb)
        else:
            from datetime import datetime as _dt, timedelta as _td
            end = _dt.now(); start = end - _td(days=5 * 365)
            features, returns, dates = predictor_service.collect_training_data(symbol, start, end)
            zoo = predictor_service.correlation_engine.train_model_zoo(features, returns)
            if not zoo:
                raise RuntimeError("not enough data")
            predictor_service.is_trained = True
            result = {"success": True, "symbol": symbol, "mode": "5y",
                      "samples": int(zoo["samples"]),
                      "history_start": str(dates[0].date()) if len(dates) else None,
                      "history_end": str(dates[-1].date()) if len(dates) else None,
                      "years_covered": round((dates[-1] - dates[0]).days / 365.2425, 1) if len(dates) else 0,
                      "zoo": zoo}
        job["stage"] = "done"
        job["result"] = result
        job["progress"] = 100
    except Exception as exc:
        logger.error(f"zoo job {job_id} failed: {exc}")
        job["stage"] = "failed"
        job["error"] = str(exc)


@router.post("/train/zoo")
async def train_model_zoo(req: ZooTrainRequest):
    """T5 + T7: 12-model leaderboard with time-series CV, optionally on the
    stock's ENTIRE available history (period=max, per-day planetary features).

    Long trainings run as a background job — poll GET /train/zoo/status."""
    key = _zoo_job_key(req.symbol, req.use_vedic, req.full_history)
    with _ZOO_LOCK:
        existing = _ZOO_JOBS.get(key)
        if existing and existing["stage"] in ("running",):
            return {"success": True, "status": "running", "job": key,
                    "stage": existing["stage"], "progress": existing["progress"]}
        if existing and existing["stage"] == "done" and (existing["result"] or {}).get("success"):
            return {"success": True, "status": "done", "job": key, **(existing["result"] or {})}
    job = {"stage": "starting", "progress": 5, "result": None, "error": None}
    _ZOO_JOBS[key] = job
    t = __import__("threading").Thread(target=_run_zoo_job, args=(key, req.symbol, req.use_vedic, req.full_history), daemon=True)
    t.start()
    return {"success": True, "status": "started", "job": key}


@router.get("/train/zoo/status")
async def zoo_status(symbol: str = "^GSPC", vedic: bool = False, full_history: bool = True):
    key = _zoo_job_key(symbol, vedic, full_history)
    job = _ZOO_JOBS.get(key)
    if not job:
        return {"success": True, "status": "idle", "job": key}
    if job["stage"] == "failed":
        return {"success": False, "status": "failed", "job": key, "error": job["error"]}
    if job["stage"] == "done":
        return {"success": True, "status": "done", "job": key, **(job["result"] or {})}
    return {"success": True, "status": "running", "job": key, "stage": job["stage"]}


@router.get("/analytics/charts/{symbol}")
async def get_analytics_charts(symbol: str):
    """T1 + round-3: trend charts, heatmap, indicators, statistical memory,
    cross-asset correlations, Monte-Carlo fan forecast and setup-analog
    predictions — every chart carries a plain-English actionable interpretation."""
    try:
        df = market_service.fetch_historical_data(symbol, period="max", interval="1d")
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No market data for {symbol}")
        # benchmark closes for the correlation block (each failure is skipped)
        BENCH_NAMES = {"SPY": "S&P 500 ETF", "QQQ": "Nasdaq-100 ETF", "^FTSE": "FTSE 100",
                       "^NSEI": "Nifty 50", "GC=F": "Gold", "TLT": "20y+ Treasuries",
                       "BTC-USD": "Bitcoin"}
        closes: Dict[str, pd.Series] = {}
        if CORR_BENCHMARKS_ENABLED:
            for b in list(BENCH_NAMES.keys()):
                try:
                    bdf = market_service.fetch_historical_data(b, period="1y", interval="1d")
                    if not bdf.empty and len(bdf) > 60:
                        closes[b] = bdf["Close"]
                except Exception as be:
                    logger.warning(f"benchmark {b} unavailable: {be}")
        pack = build_analytics(df, symbol, benchmark_closes=closes,
                               benchmark_names=BENCH_NAMES if closes else None)
        if not pack.get("success"):
            raise HTTPException(status_code=400, detail=pack.get("error", "insufficient data"))
        return pack
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"analytics charts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- T3: 45-day sky events annotated with symbol-specific meanings ----------

def _event_meaning(ev: Dict, symbol_name: str, trend: str, vol_state: str) -> str:
    etype = ev.get("type", "")
    if etype == "conjunction":
        base = "energies merge — momentum tends to accelerate in one direction"
        act = ("watch for a strong directional day; trail stops up if long" if trend == "up"
               else "wait for the spike to fade before shorting — conjunctions often start trends")
    elif etype == "opposition":
        base = "two forces pull apart — reversal and gap risk peak"
        act = ("take partial profits into the date, keep stops wide" if trend == "up"
               else "cover shorts into the panic and let the dust settle")
    elif etype == "square":
        base = "friction — choppy, whipsaw-prone ranges dominate"
        act = "cut position size by half; range trades beat trend trades this week"
    elif etype in ("trine", "sextile"):
        base = "energy flows smoothly — trend continuation is favoured"
        act = ("add on intraday dips; hold winners longer than usual" if trend == "up"
               else "bounces are likely to fail — patient shorting works")
    elif etype == "ingress":
        base = "a planet changes sign — market leadership rotates"
        act = "rotate exposure toward sectors ruled by the new sign; avoid stale themes"
    elif etype == "lunar_phase":
        if "Full" in ev.get("event", ""):
            base = "full moons mark emotional peaks — sentiment extremes"
            act = "sell into strength or collect premium (covered calls / credit spreads)"
        elif "New" in ev.get("event", ""):
            base = "new moons mark fresh starts — accumulation days"
            act = "start staged entries in quality names over the following week"
        else:
            base = "quarter moons mark decision points — trend health checks"
            act = "review stops and hold the plan unless price breaks the range"
    else:
        base = "notable sky event"; act = "observe, don't overreact"
    vol_note = f" With volatility {vol_state}, expect amplified moves." if vol_state == "elevated" else ""
    return f"For {symbol_name}: {base} — {act}.{vol_note}"


@router.get("/events/forecast")
async def get_events_forecast(symbol: str = "^GSPC", days: int = 45):
    """T3: next `days` sky events × dynamic meaning for the selected stock."""
    try:
        days = max(7, min(90, days))
        base = await get_astro_events(days=days)
        events = base.get("events", [])
        # symbol context: 3-month trend + vol state
        hist = market_service.fetch_historical_data(symbol, period="6mo", interval="1d").dropna(subset=["Close"])
        trend = "up"
        vol_state = "normal"
        if len(hist) > 63:
            chg = float(hist["Close"].iloc[-1] / hist["Close"].iloc[-63] - 1)
            trend = "up" if chg > 0.02 else ("down" if chg < -0.02 else "sideways")
            rets = hist["Close"].pct_change().dropna()
            v21 = float(rets.tail(21).std() * np.sqrt(252))
            vfull = float(rets.std() * np.sqrt(252))
            if v21 > vfull * 1.3: vol_state = "elevated"
        sym_info = market_service.get_symbol_info(symbol)
        symbol_name = sym_info.get("name", symbol) if isinstance(sym_info, dict) else symbol
        # keep only decision-grade events: drop fast-moving Moon transits
        # (they fire daily) but KEEP Full/New Moon phases — those matter.
        decision_grade = []
        for ev in events:
            title = ev.get("event", "")
            if title.startswith("Moon ") and ev.get("type") == "lunar_phase":
                decision_grade.append(ev)
            elif not title.startswith("Moon "):
                decision_grade.append(ev)
        decision_grade.sort(key=lambda e: (e.get("date", ""), 0 if e.get("significance") == "High" else 1))
        for ev in decision_grade:
            ev["meaning"] = _event_meaning(ev, symbol_name, trend, vol_state)
        return {"success": True, "symbol": symbol, "symbol_name": symbol_name,
                "trend": trend, "vol_state": vol_state, "days": days,
                "events": decision_grade, "count": len(decision_grade)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"events forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- T2: Suri cycles — detailed & actionable --------------------------------

@router.get("/suri/cycles/{symbol}")
async def get_suri_cycles(symbol: str):
    """T2: expanded Suri cycle picture — 30-day lunar journey, upcoming sign
    ingresses & retro stations, and a plain-English 'how to trade this week'
    playbook tied to the selected symbol."""
    try:
        today = datetime.utcnow().date()
        today_s = today.strftime("%Y-%m-%d")
        hist = market_service.fetch_historical_data(symbol, period="1y", interval="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No market data for {symbol}")
        closes = [float(c) for c in hist["Close"].dropna().tolist()]
        spot = closes[-1]

        # 30-day lunar journey
        lunar_journey = []
        jd0 = suri_engine._jd(today_s)
        for i in range(30):
            jd = jd0 + i
            ang = suri_engine._moon_phase_angle(jd) % 360
            names = [(0, "New Moon"), (45, "Waxing Crescent"), (90, "First Quarter"),
                     (135, "Waxing Gibbous"), (180, "Full Moon"), (225, "Waning Gibbous"),
                     (270, "Last Quarter"), (315, "Waning Crescent")]
            phase = names[0][1]
            for start, nm in names:
                if ang >= start: phase = nm
            d = today + timedelta(days=i)
            note = ("accumulation bias" if 0 <= ang < 90 else
                    "momentum bias — trends run" if 90 <= ang < 180 else
                    "distribution bias — take profits" if 180 <= ang < 270 else
                    "washout bias — prepare entries")
            lunar_journey.append({"date": d.isoformat(), "angle": round(ang, 1),
                                  "phase": phase, "note": note})

        # upcoming sidereal ingresses (Mercury, Venus, Mars, Jupiter, Saturn, Sun)
        ingresses = []
        planet_ids = {"Sun": swe.SUN, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
                      "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN}
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        for name, pid in planet_ids.items():
            try:
                lon0 = suri_engine._sidereal_lon(jd0, pid)
                sign0 = int(lon0 // 30)
                crossed = False
                for i in range(1, 61):
                    lon = suri_engine._sidereal_lon(jd0 + i, pid)
                    if int(lon // 30) != sign0:
                        ingresses.append({"date": (today + timedelta(days=i)).isoformat(),
                                          "planet": name, "into": signs[int(lon // 30)]})
                        crossed = True
                        break
            except Exception:
                continue
        ingresses.sort(key=lambda x: x["date"])

        # retrograde stations (Mercury/Venus/Mars) in next 45 days
        stations = []
        for name, pid in {"Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS}.items():
            try:
                prev_speed = None
                for i in range(0, 46):
                    jd = jd0 + i
                    pos, _ = swe.calc_ut(jd, pid)
                    sp = pos[3]
                    if prev_speed is not None and prev_speed * sp < 0:
                        d = today + timedelta(days=i)
                        kind = "turns retrograde" if sp < 0 else "turns direct"
                        stations.append({"date": d.isoformat(), "planet": name, "event": kind,
                                         "meaning": (f"{name} {kind} — plans stall, then reverse; "
                                                     "avoid fresh entries within ±2 days")})
                    prev_speed = sp
            except Exception:
                continue
        stations.sort(key=lambda x: x["date"])

        # composite + alerts for the playbook
        mood = suri_engine.market_mood(today_s)
        comp = suri_engine.composite_signal(symbol, closes)
        alerts = suri_engine.timing_alerts(today_s, days=14)
        rng = suri_engine.five_day_range(symbol, spot, closes, horizon=5)

        zone = comp.get("zone", "Neutral")
        playbook = (
            f"This week for {symbol}: the composite reads {comp.get('composite', 0):+.1f} ({zone}) with mood "
            f"{mood.get('mood_index', 50):.0f}/100. "
            + ("Lean long: buy early-week dips toward the 50-day average and hold through the moon's waxing phase. "
               if zone in ("Buy", "Strong Buy") else
               "Lean defensive: sell covered calls / credit spreads into bounces and keep stops intact. "
               if zone in ("Sell", "Strong Sell") else
               "Stay balanced: trade the range — buy near range floor, sell near range ceiling, small size. ")
            + (f"Key dates to respect: " + ", ".join(a["date"] for a in alerts[:4]) + "." if alerts else
               "No major reversal windows this week — plan around routine levels.")
        )
        return {
            "success": True, "symbol": symbol, "date": today_s, "spot": _f(spot),
            "lunar_journey": lunar_journey,
            "ingresses": ingresses,
            "stations": stations,
            "playbook": playbook,
            "mood": mood, "composite": comp, "five_day_range": rng,
            "timing_alerts": alerts,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"suri cycles error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- T11: TradingAgents-style multi-agent analysis ---------------------------

@router.get("/agents/{symbol}")
async def get_agents_analysis(symbol: str):
    """T11: seven specialist agents debate the selected symbol; a fund manager
    gives the final plain-English verdict."""
    try:
        stats_raw = await get_quant_stats(symbol, 3)
        risk_raw = await get_quant_risk(symbol, 3)
        astro = await get_astro_signal(symbol)
        _, rets_1y = _load_returns(symbol, 1)
        perf_1y = float((1.0 + pd.Series(rets_1y)).prod() - 1.0) * 100 if len(rets_1y) else 0.0
        sym_info = market_service.get_symbol_info(symbol)
        symbol_name = sym_info.get("name", symbol) if isinstance(sym_info, dict) else symbol
        result = agents_engine.analyse(symbol, symbol_name,
                                       stats={"performance": {"1y": perf_1y},
                                              "risk": {
                                                  "max_drawdown_pct": float(stats_raw.get("stats", {}).get("max_drawdown", -0.15) or 0.0) * 100,
                                                  "var_95": float(risk_raw.get("risk", {}).get("var_hist_usd", 0) or 0),
                                              }},
                                       astro=astro, events=[])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"agents analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- T8/T9/T10: repo concept coverage matrix ---------------------------------

@router.get("/concepts")
async def get_concepts():
    """Coverage matrix: 28 audited repositories → concepts → where they live
    in AstroTrader → the plain-English trading meaning of each concept."""
    return all_concepts()
