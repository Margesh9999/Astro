"""
Correlation analysis between planetary data and market data
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet, BayesianRidge
from sklearn.ensemble import (RandomForestRegressor, GradientBoostingRegressor,
                              ExtraTreesRegressor, AdaBoostRegressor,
                              HistGradientBoostingRegressor)
from sklearn.neighbors import KNeighborsRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.pipeline import make_pipeline

logger = logging.getLogger(__name__)

MODEL_ZOO_SPEC = {
    "linear_regression": lambda: LinearRegression(),
    "ridge": lambda: Ridge(alpha=1.0),
    "lasso": lambda: Lasso(alpha=0.0005, max_iter=5000),
    "elastic_net": lambda: ElasticNet(alpha=0.0005, l1_ratio=0.5, max_iter=5000),
    "knn": lambda: KNeighborsRegressor(n_neighbors=15, weights="distance"),
    "decision_tree": lambda: DecisionTreeRegressor(max_depth=8, random_state=42),
    "bayesian_ridge": lambda: BayesianRidge(),
    "random_forest": lambda: RandomForestRegressor(n_estimators=100, max_depth=14, min_samples_leaf=5,
                                                    random_state=42, n_jobs=2),
    "extra_trees": lambda: ExtraTreesRegressor(n_estimators=100, max_depth=14, min_samples_leaf=5,
                                               random_state=42, n_jobs=2),
    "gradient_boosting": lambda: GradientBoostingRegressor(n_estimators=80, learning_rate=0.07,
                                                           max_depth=2, subsample=0.8, random_state=42),
    "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(max_iter=150, learning_rate=0.06, random_state=42),
    "ada_boost": lambda: AdaBoostRegressor(n_estimators=60, random_state=42),
    "mlp": lambda: MLPRegressor(hidden_layer_sizes=(32, 16), max_iter=200, early_stopping=True,
                                random_state=42),
}

MODEL_NOTES = {
    "linear_regression": "fits a straight-line relationship — the simplest baseline; easy to trust, easy to beat",
    "ridge": "a straight line that resists over-fitting by shrinking extreme weights",
    "lasso": "a straight line that automatically zeroes-out useless planetary features",
    "elastic_net": "a blend of ridge and lasso — robust all-round linear model",
    "knn": "predicts from the most similar past days — a pattern-matcher that loves repeated setups",
    "decision_tree": "one interpretable if-then rule tree — shows exactly which planet combos matter",
    "bayesian_ridge": "a probabilistic straight line — gives confident averages instead of wild guesses",
    "random_forest": "an ensemble of decision trees — captures planet-combination rules, hard to over-fit",
    "extra_trees": "an even more randomised forest — often generalises better on noisy financial data",
    "gradient_boosting": "trees built one after another, each fixing the previous errors — usually the top performer",
    "hist_gradient_boosting": "a fast modern boosting model (LightGBM-style) — excellent on large histories",
    "ada_boost": "boosting that re-weights the hardest days — good at catching rare regimes",
    "mlp": "a small neural network — flexible but needs more data to shine",
}

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
            model_type: Type of model to use ('linear_regression', 'random_forest' or any zoo key)

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
        elif model_type in getattr(self, 'zoo', {}):
            return self.zoo[model_type].predict(features_scaled)
        else:
            logger.error(f"Unknown model type: {model_type}")
            return np.array([])

    # ------------------------------------------------------------------
    # T5 — 12-model zoo with time-series cross-validation
    # ------------------------------------------------------------------
    def train_model_zoo(
        self,
        planetary_features: np.ndarray,
        market_returns: np.ndarray,
        n_splits: int = 4,
        progress_cb=None,
    ) -> Dict[str, any]:
        """
        Train the full model zoo and rank by time-series CV R².

        Returns a leaderboard with per-model metrics, the winning model name,
        feature importance from the best tree model, and an English analysis.
        """
        X = np.asarray(planetary_features, dtype=float)
        y = np.asarray(market_returns, dtype=float)
        if len(X) < 60:
            return {}

        leaderboard = []
        self.zoo: Dict[str, any] = {}
        best_name, best_r2, best_pipeline = None, -1e9, None

        # cap per-fold train size so 100-year histories stay fast; the FINAL
        # model below is still fit on the ENTIRE history
        tscv = TimeSeriesSplit(n_splits=n_splits, max_train_size=8000)
        for name, factory in MODEL_ZOO_SPEC.items():
            try:
                scores = []
                for tr_idx, te_idx in tscv.split(X):
                    pipe = make_pipeline(StandardScaler(), factory())
                    pipe.fit(X[tr_idx], y[tr_idx])
                    pred = pipe.predict(X[te_idx])
                    scores.append(r2_score(y[te_idx], pred))
                mean_r2 = float(np.mean(scores))
                # final fit on ALL data
                pipe_full = make_pipeline(StandardScaler(), factory())
                pipe_full.fit(X, y)
                self.zoo[name] = pipe_full.steps[-1][1]
                leaderboard.append({
                    "model": name,
                    "cv_r2": round(mean_r2, 5),
                    "cv_r2_folds": [round(float(s), 5) for s in scores],
                    "note": MODEL_NOTES.get(name, ""),
                })
                if mean_r2 > best_r2:
                    best_name, best_r2, best_pipeline = name, mean_r2, pipe_full
                if progress_cb:
                    progress_cb(name, len(leaderboard), len(MODEL_ZOO_SPEC))
            except Exception as exc:
                logger.warning(f"Model {name} failed: {exc}")

        if best_pipeline is None:
            return {}

        leaderboard.sort(key=lambda m: m["cv_r2"], reverse=True)

        # feature importance: prefer the best tree model that exposes it
        importance = []
        for entry in leaderboard:
            mdl = self.zoo.get(entry["model"])
            imp = getattr(mdl, "feature_importances_", None)
            if imp is not None:
                pairs = sorted(zip(self.feature_names, imp), key=lambda p: p[1], reverse=True)
                importance = [{"feature": f, "importance": round(float(v), 5)} for f, v in pairs[:15]]
                break

        spread = leaderboard[0]["cv_r2"] - leaderboard[-1]["cv_r2"]
        analysis = (
            f"Trained {len(leaderboard)} model families on {len(X)} days of history using walk-forward "
            f"time-series validation. The winner is {leaderboard[0]['model']} "
            f"(CV R² {leaderboard[0]['cv_r2']:+.4f} vs {leaderboard[-1]['model']} at "
            f"{leaderboard[-1]['cv_r2']:+.4f}). "
            f"{MODEL_NOTES.get(leaderboard[0]['model'], '')[:1].upper()}"
            f"{MODEL_NOTES.get(leaderboard[0]['model'], '')[1:]}. "
            + ("Financial returns are mostly noise — an R² near zero is NORMAL; the ranking, not the absolute value, is the signal. "
               if best_r2 < 0.02 else
               "An unusually high R² — treat with caution, verify on fresh data before trusting it. ")
            + f"Use the winning model for predictions; keep the leaderboard as your evidence trail."
        )

        return {
            "leaderboard": leaderboard,
            "best_model": best_name,
            "best_cv_r2": best_r2,
            "feature_importance": importance,
            "analysis": analysis,
            "samples": len(X),
        }

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