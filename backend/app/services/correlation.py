"""
Correlation analysis between planetary data and market data
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error

logger = logging.getLogger(__name__)

class CorrelationEngine:
    """Engine for finding correlations between planetary features and market returns"""

    def __init__(self):
        """Initialize correlation engine"""
        self.scaler = StandardScaler()
        self.linear_model = LinearRegression()
        self.rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.feature_names = []
        logger.info("CorrelationEngine initialized")

    def prepare_planetary_features(
        self,
        planetary_data: List[Dict],
        include_aspects: bool = True,
        vedic: bool = False
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Convert planetary data to feature matrix

        Args:
            planetary_data: List of dictionaries with planetary data for each timestamp
            include_aspects: Whether to include aspect features
            vedic: Whether to use Vedic calculations

        Returns:
            Tuple of (feature_matrix, feature_names)
        """
        if not planetary_data:
            return np.array([]), []

        features_list = []

        for i, planet_dict in enumerate(planetary_data):
            # Features from each planet
            planet_features = {}

            # Process each entry in the dictionary
            for entry_name, entry_data in planet_dict.items():
                if entry_name == 'timestamp':
                    continue

                # Non-dict entries are scalar features (e.g. aspect_score_*)
                if not isinstance(entry_data, dict):
                    planet_features[entry_name] = float(entry_data) if entry_data is not None else 0.0
                    continue

                planet_name = entry_name
                planet_data = entry_data

                # Basic planetary features
                prefix = f"{planet_name.lower()}_"
                planet_features[f"{prefix}longitude"] = planet_data.get('longitude', 0)
                planet_features[f"{prefix}latitude"] = planet_data.get('latitude', 0)
                planet_features[f"{prefix}speed"] = planet_data.get('speed_longitude', 0)
                planet_features[f"{prefix}distance"] = planet_data.get('distance', 0)
                planet_features[f"{prefix}retrograde"] = 1 if planet_data.get('is_retrograde', False) else 0

                # Sign encoding (one-hot for zodiac sign)
                sign = planet_data.get('sign', 'Aries')
                sign_map = {
                    'Aries': 0, 'Taurus': 1, 'Gemini': 2, 'Cancer': 3, 'Leo': 4, 'Virgo': 5,
                    'Libra': 6, 'Scorpio': 7, 'Sagittarius': 8, 'Capricorn': 9, 'Aquarius': 10, 'Pisces': 11
                }
                sign_num = sign_map.get(sign, 0)
                for i_sign in range(12):
                    planet_features[f"{prefix}sign_{i_sign}"] = 1 if i_sign == sign_num else 0

                # Degree within sign
                planet_features[f"{prefix}degree"] = planet_data.get('degree_within_sign', 0)

                # Vedic-specific features
                if vedic:
                    planet_features[f"{prefix}nakshatra"] = planet_data.get('nakshatra_index', 0)
                    planet_features[f"{prefix}pada"] = planet_data.get('pada', 1)
                    planet_features[f"{prefix}ayanamsa"] = planet_data.get('ayanamsa', 0)

            features_list.append(planet_features)

        # Convert to DataFrame for easier handling
        df_features = pd.DataFrame(features_list)

        # Add aspect features if requested
        if include_aspects and len(planetary_data) > 0:
            # This is a simplified approach - in practice, you'd calculate aspects
            # for each timestamp and add them as features
            pass

        # Fill NaN values with 0
        df_features = df_features.fillna(0)

        # Store feature names
        self.feature_names = df_features.columns.tolist()

        return df_features.values, self.feature_names

    def calculate_correlations(
        self,
        planetary_features: np.ndarray,
        market_returns: np.ndarray
    ) -> Dict[str, float]:
        """
        Calculate correlations between each planetary feature and market returns

        Args:
            planetary_features: Feature matrix (n_samples, n_features)
            market_returns: Target returns array (n_samples,)

        Returns:
            Dictionary mapping feature names to correlation coefficients
        """
        if len(planetary_features) == 0 or len(market_returns) == 0:
            return {}

        if planetary_features.shape[0] != len(market_returns):
            logger.error("Feature and target arrays must have same number of samples")
            return {}

        correlations = {}

        # Calculate correlation for each feature
        for i, feature_name in enumerate(self.feature_names):
            feature_values = planetary_features[:, i]
            # Calculate Pearson correlation
            if np.std(feature_values) > 0 and np.std(market_returns) > 0:
                corr = np.corrcoef(feature_values, market_returns)[0, 1]
                # Handle NaN values
                if not np.isnan(corr):
                    correlations[feature_name] = float(corr)
                else:
                    correlations[feature_name] = 0.0
            else:
                correlations[feature_name] = 0.0

        return correlations

    def train_models(
        self,
        planetary_features: np.ndarray,
        market_returns: np.ndarray,
        test_size: float = 0.2
    ) -> Dict[str, any]:
        """
        Train linear and random forest models

        Args:
            planetary_features: Feature matrix
            market_returns: Target returns
            test_size: Fraction of data to use for testing

        Returns:
            Dictionary with trained models and performance metrics
        """
        if len(planetary_features) == 0 or len(market_returns) == 0:
            return {}

        if planetary_features.shape[0] < 10:
            logger.warning("Too few samples for training")
            return {}

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            planetary_features, market_returns, test_size=test_size, random_state=42
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train linear regression
        self.linear_model.fit(X_train_scaled, y_train)
        y_pred_linear = self.linear_model.predict(X_test_scaled)
        linear_r2 = r2_score(y_test, y_pred_linear)
        linear_mse = mean_squared_error(y_test, y_pred_linear)

        # Train random forest
        self.rf_model.fit(X_train_scaled, y_train)
        y_pred_rf = self.rf_model.predict(X_test_scaled)
        rf_r2 = r2_score(y_test, y_pred_rf)
        rf_mse = mean_squared_error(y_test, y_pred_rf)

        # Feature importance from random forest
        feature_importance = dict(zip(self.feature_names, self.rf_model.feature_importances_))

        results = {
            'linear_regression': {
                'model': self.linear_model,
                'r2_score': linear_r2,
                'mse': linear_mse,
                'predictions': y_pred_linear
            },
            'random_forest': {
                'model': self.rf_model,
                'r2_score': rf_r2,
                'mse': rf_mse,
                'predictions': y_pred_rf
            },
            'feature_importance': feature_importance,
            'test_size': len(y_test),
            'train_size': len(y_train)
        }

        logger.info(f"Models trained - Linear R²: {linear_r2:.4f}, RF R²: {rf_r2:.4f}")
        return results

    def predict_returns(
        self,
        planetary_features: np.ndarray,
        model_type: str = 'random_forest'
    ) -> np.ndarray:
        """
        Predict market returns using trained model

        Args:
            planetary_features: Feature matrix for prediction
            model_type: Type of model to use ('linear_regression' or 'random_forest')

        Returns:
            Array of predicted returns
        """
        if len(planetary_features) == 0:
            return np.array([])

        # Scale features
        features_scaled = self.scaler.transform(planetary_features)

        if model_type == 'linear_regression':
            return self.linear_model.predict(features_scaled)
        elif model_type == 'random_forest':
            return self.rf_model.predict(features_scaled)
        else:
            logger.error(f"Unknown model type: {model_type}")
            return np.array([])

    def get_top_features(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get top N features by importance from random forest model

        Args:
            n: Number of top features to return

        Returns:
            List of (feature_name, importance) tuples sorted by importance
        """
        if not hasattr(self.rf_model, 'feature_importances_'):
            return []

        # Get feature importances
        importances = self.rf_model.feature_importances_
        feature_importance_pairs = list(zip(self.feature_names, importances))

        # Sort by importance (descending)
        sorted_pairs = sorted(feature_importance_pairs, key=lambda x: x[1], reverse=True)

        return sorted_pairs[:n]