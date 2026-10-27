"""
Prediction service that combines planetary data with market data to generate forecasts
"""
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from app.core.ephemeris import EphemerisCalculator
from app.core.aspects import AspectsCalculator
from app.core.vedic import VedicCalculator
from app.services.market_data import MarketDataService
from app.services.correlation import CorrelationEngine

logger = logging.getLogger(__name__)

class PredictorService:
    """Service for generating market predictions based on planetary data"""

    def __init__(
        self,
        ephe_path: str = "",
        cache_dir: str = "./data",
        use_vedic: bool = False
    ):
        """
        Initialize predictor service

        Args:
            ephe_path: Path to Swiss Ephemeris files
            cache_dir: Directory for caching data
            use_vedic: Whether to use Vedic calculations
        """
        self.ephemeris = EphemerisCalculator(ephe_path)
        self.aspects_calculator = AspectsCalculator()
        self.vedic_calculator = VedicCalculator() if use_vedic else None
        self.market_data = MarketDataService(cache_dir)
        self.correlation_engine = CorrelationEngine()
        self.use_vedic = use_vedic
        self.is_trained = False
        logger.info(f"PredictorService initialized (vedic: {use_vedic})")

    def collect_training_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        step_hours: int = 24
    ) -> Tuple[np.ndarray, np.ndarray, List[datetime]]:
        """
        Collect planetary and market data for training

        Args:
            symbol: Market symbol to analyze
            start_date: Start date for data collection
            end_date: End date for data collection
            step_hours: Hours between data points

        Returns:
            Tuple of (features, returns, timestamps)
        """
        try:
            # Fetch market data
            market_df = self.market_data.fetch_historical_data(
                symbol,
                period=f"{(end_date - start_date).days}d",
                interval="1d"
            )

            if market_df.empty:
                logger.error(f"No market data fetched for {symbol}")
                return np.array([]), np.array([]), []

            # Align features to ACTUAL market trading dates so that each
            # feature row corresponds exactly to the return of that session.
            dates = []
            returns = []
            planetary_data_list = []

            for date_idx, row in market_df.iterrows():
                if isinstance(date_idx, str):
                    dt = pd.to_datetime(date_idx).to_pydatetime()
                else:
                    dt = date_idx.to_pydatetime() if hasattr(date_idx, 'to_pydatetime') else date_idx
                # Normalize to midnight UTC-naive for ephemeris lookups
                dt = dt.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)

                if not (start_date <= dt <= end_date):
                    continue

                ret = row['Returns'] if not pd.isna(row['Returns']) else 0.0

                # Get Julian day for this trading date
                julian_day = self.ephemeris.date_to_julian(dt)

                # Get planetary positions
                if self.use_vedic and self.vedic_calculator is not None:
                    planetary_positions = self.vedic_calculator.calculate_all_planets_vedic(julian_day)
                else:
                    planetary_positions = self.ephemeris.calculate_all_planets(julian_day)

                # Calculate aspects
                aspects = self.aspects_calculator.calculate_all_aspects(planetary_positions)

                # Combine planetary data with aspects for this timestamp
                timestamp_data = {
                    **planetary_positions,
                    'aspect_score_conjunction': self.aspects_calculator.get_aspect_score(aspects, 'conjunction'),
                    'aspect_score_opposition': self.aspects_calculator.get_aspect_score(aspects, 'opposition'),
                    'aspect_score_trine': self.aspects_calculator.get_aspect_score(aspects, 'trine'),
                    'aspect_score_square': self.aspects_calculator.get_aspect_score(aspects, 'square'),
                    'aspect_score_sextile': self.aspects_calculator.get_aspect_score(aspects, 'sextile'),
                }

                dates.append(dt)
                returns.append(float(ret))
                planetary_data_list.append(timestamp_data)

            if not dates:
                logger.error("No valid dates found in market data")
                return np.array([]), np.array([]), []

            features, feature_names = self.correlation_engine.prepare_planetary_features(
                planetary_data_list,
                include_aspects=False,  # We already added aspect scores above
                vedic=self.use_vedic
            )

            # Align lengths defensively
            min_length = min(len(features), len(returns))
            features = features[:min_length]
            returns_array = np.array(returns[:min_length])
            dates_aligned = dates[:min_length]

            logger.info(f"Collected {len(features)} samples for training")
            return features, returns_array, dates_aligned

        except Exception as e:
            logger.error(f"Error collecting training data: {e}")
            return np.array([]), np.array([]), []

    def train_model(
        self,
        symbol: str = "^GSPC",
        lookback_years: int = 5
    ) -> Dict[str, any]:
        """
        Train the prediction model

        Args:
            symbol: Market symbol to train on
            lookback_years: Years of historical data to use

        Returns:
            Dictionary with training results
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_years * 365)

            logger.info(f"Training model for {symbol} from {start_date.date()} to {end_date.date()}")

            # Collect training data
            features, returns, dates = self.collect_training_data(symbol, start_date, end_date)

            if len(features) == 0:
                logger.error("No training data collected")
                return {'success': False, 'error': 'No training data'}

            # Train the correlation models
            results = self.correlation_engine.train_models(features, returns)

            if not results:
                logger.error("Model training failed")
                return {'success': False, 'error': 'Model training failed'}

            self.is_trained = True
            self.last_trained_symbol = symbol
            self.last_trained_date = end_date

            logger.info(f"Model training completed successfully for {symbol}")
            return {
                'success': True,
                'symbol': symbol,
                'samples': len(features),
                'date_range': f"{start_date.date()} to {end_date.date()}",
                'linear_r2': results['linear_regression']['r2_score'],
                'rf_r2': results['random_forest']['r2_score'],
                'feature_importance': results['feature_importance']
            }

        except Exception as e:
            logger.error(f"Error during model training: {e}")
            return {'success': False, 'error': str(e)}

    def predict_future(
        self,
        symbol: str = "^GSPC",
        days_ahead: int = 30
    ) -> Dict[str, any]:
        """
        Generate future predictions based on planetary positions

        Args:
            symbol: Market symbol to predict
            days_ahead: Number of days to predict ahead

        Returns:
            Dictionary with predictions and metadata
        """
        if not self.is_trained:
            logger.warning("Model not trained. Attempting to train now...")
            train_result = self.train_model(symbol)
            if not train_result['success']:
                return train_result

        try:
            # Calculate future planetary positions
            start_date = datetime.now()
            end_date = start_date + timedelta(days=days_ahead)

            future_dates = []
            future_features_list = []

            current_date = start_date
            while current_date <= end_date:
                # Get Julian day
                julian_day = self.ephemeris.date_to_julian(current_date)

                # Get planetary positions
                if self.use_vedic:
                    planetary_positions = self.vedic_calculator.calculate_all_planets_vedic(julian_day)
                else:
                    planetary_positions = self.ephemeris.calculate_all_planets(julian_day)

                # Calculate aspects
                aspects = self.aspects_calculator.calculate_all_aspects(planetary_positions)

                # Combine data
                timestamp_data = {
                    'timestamp': current_date,
                    **planetary_positions
                }

                # Add aspect summary features
                timestamp_data['aspect_score_conjunction'] = self.aspects_calculator.get_aspect_score(aspects, 'conjunction')
                timestamp_data['aspect_score_opposition'] = self.aspects_calculator.get_aspect_score(aspects, 'opposition')
                timestamp_data['aspect_score_trine'] = self.aspects_calculator.get_aspect_score(aspects, 'trine')
                timestamp_data['aspect_score_square'] = self.aspects_calculator.get_aspect_score(aspects, 'square')
                timestamp_data['aspect_score_sextile'] = self.aspects_calculator.get_aspect_score(aspects, 'sextile')

                future_features_list.append(timestamp_data)
                future_dates.append(current_date)
                current_date += timedelta(days=1)

            # Prepare features
            planetary_only_data = []
            for data in future_features_list:
                timestamp = data.pop('timestamp')
                planetary_only_data.append(data)

            features, _ = self.correlation_engine.prepare_planetary_features(
                planetary_only_data,
                include_aspects=False,
                vedic=self.use_vedic
            )

            if len(features) == 0:
                return {'success': False, 'error': 'Could not generate future features'}

            # Generate predictions
            predictions = self.correlation_engine.predict_returns(features, 'random_forest')

            # Calculate cumulative returns for price projection
            cumulative_returns = np.cumprod(1 + predictions) - 1

            # Get current price for reference
            current_price = self.market_data.get_real_time_price(symbol)
            if current_price is None:
                # Fallback to last known price
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="1d")
                    current_price = float(hist['Close'].iloc[-1]) if not hist.empty else 100.0
                except:
                    current_price = 100.0  # Default fallback

            # Project future prices
            projected_prices = current_price * (1 + cumulative_returns)

            # Prepare results
            results = {
                'success': True,
                'symbol': symbol,
                'current_price': float(current_price),
                'prediction_days': days_ahead,
                'dates': [dt.isoformat() for dt in future_dates],
                'daily_returns': predictions.tolist(),
                'cumulative_returns': cumulative_returns.tolist(),
                'projected_prices': projected_prices.tolist(),
                'model_used': 'random_forest',
                'vedic': self.use_vedic
            }

            logger.info(f"Generated {days_ahead}-day prediction for {symbol}")
            return results

        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
            return {'success': False, 'error': str(e)}

    def get_feature_importance(self) -> List[Tuple[str, float]]:
        """
        Get feature importance from the trained model

        Returns:
            List of (feature_name, importance) tuples
        """
        if not self.is_trained:
            return []
        return self.correlation_engine.get_top_features(15)
    # ------------------------------------------------------------------
    # T7 — full-history training from the stock's inception
    # ------------------------------------------------------------------
    def _features_cache_path(self, symbol: str, vedic: bool) -> str:
        import os
        return os.path.join(self.market_data.cache_dir, f"features_{symbol.replace('^','idx_').replace('.','_')}_{int(vedic)}.pkl")

    def collect_full_history_data(self, symbol: str, vedic: bool = False):
        """
        Fetch period='max' history and build per-trading-day planetary features
        from the stock's INCEPTION. Results are cached to disk per symbol so
        subsequent runs are instant.

        Uses a vectorised ephemeris pass (planets outer-loop, days inner-loop)
        and numpy aspect scoring that reproduces EXACTLY the same feature
        columns — in the same order — as
        CorrelationEngine.prepare_planetary_features, so train/predict stay
        aligned.
        """
        import os
        import pickle
        import swisseph as _swe
        cache_path = self._features_cache_path(symbol, vedic)
        market_df = self.market_data.fetch_historical_data(symbol, period="max", interval="1d")
        if market_df.empty:
            return np.array([]), np.array([]), [], ""

        # disk cache keyed by the last trading date
        stamp = str(market_df.index.max().date())
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as fh:
                    blob = pickle.load(fh)
                if blob.get("stamp") == stamp:
                    return blob["features"], blob["returns"], blob["dates"], stamp
            except Exception:
                pass

        PLANETS = [("Sun", _swe.SUN), ("Moon", _swe.MOON), ("Mercury", _swe.MERCURY),
                   ("Venus", _swe.VENUS), ("Mars", _swe.MARS), ("Jupiter", _swe.JUPITER),
                   ("Saturn", _swe.SATURN), ("Uranus", _swe.URANUS),
                   ("Neptune", _swe.NEPTUNE), ("Pluto", _swe.PLUTO)]

        dates = []
        for i in market_df.index:
            d = pd.Timestamp(i).to_pydatetime()
            dates.append(d.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0))
        n = len(dates)
        jds = np.array([_swe.julday(d.year, d.month, d.day, 0.0) for d in dates])

        ayanamsa = (np.array([_swe.get_ayanamsa_ut(jd) for jd in jds])
                    if vedic else np.zeros(n))

        lons, lats, dists, speeds = {}, {}, {}, {}
        for name, pid in PLANETS:
            lon = np.empty(n); lat = np.empty(n); dist = np.empty(n); spd = np.empty(n)
            for k, jd in enumerate(jds):
                pos, _ret = _swe.calc_ut(float(jd), pid)
                lon[k], lat[k], dist[k], spd[k] = pos[0], pos[1], pos[2], pos[3]
            if vedic:
                lon = (lon - ayanamsa) % 360.0
            lons[name], lats[name], dists[name], speeds[name] = lon, lat, dist, spd

        # ---- assemble feature columns in EXACTLY prepare_planetary_features order ----
        cols: "OrderedDict[str, np.ndarray]" = {}
        for name, _pid in PLANETS:
            p = name.lower()
            lon = lons[name]
            sign_num = np.floor(lon / 30.0).astype(int) % 12
            cols[f"{p}_longitude"] = lon
            cols[f"{p}_latitude"] = lats[name]
            cols[f"{p}_speed"] = speeds[name]
            cols[f"{p}_distance"] = dists[name]
            cols[f"{p}_retrograde"] = (speeds[name] < 0).astype(float)
            for s in range(12):
                cols[f"{p}_sign_{s}"] = (sign_num == s).astype(float)
            cols[f"{p}_degree"] = lon % 30.0
            if vedic:
                nak_span = 360.0 / 27.0
                cols[f"{p}_nakshatra"] = np.floor(lon / nak_span).astype(float)
                cols[f"{p}_pada"] = (np.floor((lon % nak_span) / nak_span * 4.0) + 1.0)
                cols[f"{p}_ayanamsa"] = ayanamsa

        # ---- vectorised aspect scores (identical formula to AspectsCalculator) ----
        SPEC = {"conjunction": (0.0, 8.0, 1.0), "opposition": (180.0, 8.0, 0.8),
                "trine": (120.0, 8.0, 0.6), "square": (90.0, 8.0, 0.7),
                "sextile": (60.0, 6.0, 0.4)}
        names = [nm for nm, _ in PLANETS]
        L = np.stack([lons[nm] for nm in names])
        scores = {k: np.zeros(n) for k in SPEC}
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                d = np.abs(L[i] - L[j]) % 360.0
                diff = np.minimum(d, 360.0 - d)
                for asp, (ang, orb, w) in SPEC.items():
                    dev = np.abs(diff - ang)
                    mask = dev <= orb
                    scores[asp] += w * (1.0 - dev / orb) * mask
        for asp in ["conjunction", "opposition", "trine", "square", "sextile"]:
            cols[f"aspect_score_{asp}"] = scores[asp]

        features = pd.DataFrame(cols).values.astype(float)
        returns = market_df["Returns"].fillna(0.0).values[:n]
        m = min(len(features), len(returns))
        features, returns = features[:m], np.asarray(returns[:m], dtype=float)
        dates = dates[:m]
        try:
            with open(cache_path, "wb") as fh:
                pickle.dump({"stamp": stamp, "features": features, "returns": returns,
                             "dates": dates}, fh)
        except Exception as exc:
            logger.warning(f"features cache write failed: {exc}")
        return features, returns, dates, stamp

    def train_model_full_history(self, symbol: str = "^GSPC", use_vedic: bool = False,
                                 progress_cb=None) -> Dict[str, any]:
        """
        T7: train the model zoo on the MAXIMUM available history (inception → today).
        """
        try:
            features, returns, dates, stamp = self.collect_full_history_data(symbol, vedic=use_vedic)
            if len(features) < 60:
                return {"success": False, "error": "not enough history for full training"}
            if progress_cb:
                progress_cb(f"training 12 models on {len(features)} days", 1, 1)
            zoo = self.correlation_engine.train_model_zoo(
                features, returns,
                progress_cb=(lambda name, done, total: progress_cb(
                    f"{name} ({done}/{total})", done, total) if progress_cb else None))
            if not zoo:
                return {"success": False, "error": "model zoo training failed"}
            self.is_trained = True
            self.last_trained_symbol = symbol
            self.last_trained_date = datetime.now()
            self.last_zoo = zoo
            return {
                "success": True,
                "symbol": symbol,
                "mode": "full_history",
                "samples": int(zoo["samples"]),
                "history_start": str(dates[0].date()),
                "history_end": str(dates[-1].date()),
                "years_covered": round((dates[-1] - dates[0]).days / 365.2425, 1),
                "zoo": zoo,
            }
        except Exception as e:
            logger.error(f"full-history training failed: {e}")
            return {"success": False, "error": str(e)}
