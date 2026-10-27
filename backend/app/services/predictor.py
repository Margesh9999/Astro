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