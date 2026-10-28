"""
v1.3 Model Zoo — ~45 models across 9 families, trained on the stock's FULL
history with walk-forward (expanding-window) cross-validation.

Honest evaluation:
* every score is OUT-OF-SAMPLE: a model only ever predicts sessions that come
  after all of the data it was trained on;
* regression models are scored with R²_OS against the naive "historical mean"
  forecast (positive = beats naive), plus hit rate, information coefficient and
  a Diebold–Mariano-style t-stat versus that naive forecast;
* direction classifiers report accuracy, balanced accuracy and AUC versus the
  base rate (always guessing the majority direction);
* slow models are capped (recent N training rows per fold) — every cap is
  reported in the response so nothing is hidden.

Optional libraries (xgboost, lightgbm, catboost, statsmodels, torch) are
imported lazily: a missing one turns into a clear "skipped" status.
"""
from __future__ import annotations

import importlib
import logging
import math
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.base import clone
from sklearn.ensemble import (AdaBoostRegressor, ExtraTreesClassifier, ExtraTreesRegressor,
                              GradientBoostingRegressor, HistGradientBoostingClassifier,
                              HistGradientBoostingRegressor, RandomForestClassifier,
                              RandomForestRegressor)
from sklearn.cross_decomposition import PLSRegression
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.inspection import permutation_importance
from sklearn.linear_model import (BayesianRidge, ElasticNet, HuberRegressor, Lasso, LinearRegression,
                                  LogisticRegression, QuantileRegressor, Ridge, TheilSenRegressor)
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR, LinearSVR
from sklearn.tree import DecisionTreeRegressor

from app.services.model_features import feature_columns, feature_group, feature_meaning

logger = logging.getLogger(__name__)

N_FOLDS = 5
TOP_K = 5


def has_module(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _f(x: Any, nd: int = 6) -> Optional[float]:
    try:
        v = float(x)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return round(v, nd)


# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------
@dataclass
class Spec:
    key: str
    name: str
    family: str
    kind: str                     # reg | clf | ts | naive
    desc: str
    factory: Optional[Callable[[], Any]] = None
    cap: Optional[int] = None     # max (most recent) training rows per fold
    requires: Optional[str] = None
    scale: bool = True
    note: str = ""
    fset: str = "all"             # all | fast (no slow-planet longitudes) | core (8 technical features)
    tt: bool = False              # standardise the target too (SVR / MLP)
    par: bool = False             # single-threaded → run folds in parallel processes
    extra: Dict[str, Any] = field(default_factory=dict)


SLOW_BODIES = ("jupiter", "saturn", "rahu", "uranus", "neptune", "pluto")
CORE_FEATURES = ["ret_lag1", "ret_lag2", "mom_5", "mom_20", "mom_60", "vol_20", "rsi_14", "dist_sma200"]
FSET_LABEL = {"all": "all features",
              "fast": "all except slow-planet longitudes/signs (they act as calendar-time trends for linear models)",
              "core": "8 core technical features"}


def select_cols(feats: List[str], fset: str) -> List[int]:
    if fset == "fast":
        return [i for i, f in enumerate(feats)
                if not (f.startswith(SLOW_BODIES) and f.endswith(("lon_sin", "lon_cos", "sign")))]
    if fset == "core":
        idx = [feats.index(f) for f in CORE_FEATURES if f in feats]
        return idx or list(range(len(feats)))
    return list(range(len(feats)))


def _clip(a):
    return np.clip(a, -5.0, 5.0)


def build_model(spec: "Spec"):
    from sklearn.compose import TransformedTargetRegressor
    from sklearn.preprocessing import FunctionTransformer
    est = spec.factory()
    mdl = make_pipeline(StandardScaler(), FunctionTransformer(_clip), est) if spec.scale else est
    if spec.tt:
        mdl = TransformedTargetRegressor(regressor=mdl, transformer=StandardScaler())
    return mdl


def _fold_job(spec: "Spec", X: np.ndarray, y: np.ndarray, tr: np.ndarray, te: np.ndarray) -> np.ndarray:
    """Top-level so it can run in a worker process."""
    warnings.simplefilter("ignore")
    trc = tr[-spec.cap:] if spec.cap else tr
    mdl = build_model(spec)
    mdl.fit(X[trc], y[trc])
    if hasattr(mdl, "predict_proba") and spec.kind == "clf":
        return mdl.predict_proba(X[te])[:, 1]
    return np.asarray(mdl.predict(X[te])).ravel()


def _xgb_reg():
    import xgboost as xgb
    return xgb.XGBRegressor(n_estimators=250, max_depth=3, learning_rate=0.03, subsample=0.8,
                            colsample_bytree=0.6, min_child_weight=50, n_jobs=4, verbosity=0)


def _lgb_reg():
    import lightgbm as lgb
    return lgb.LGBMRegressor(n_estimators=300, num_leaves=15, learning_rate=0.03, subsample=0.8,
                             subsample_freq=1, colsample_bytree=0.6, min_child_samples=100,
                             n_jobs=4, verbose=-1)


def _cat_reg():
    import catboost as cb
    return cb.CatBoostRegressor(iterations=300, depth=5, learning_rate=0.05, verbose=0,
                                thread_count=4, allow_writing_files=False)


def _xgb_clf():
    import xgboost as xgb
    return xgb.XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.03, subsample=0.8,
                             colsample_bytree=0.6, min_child_weight=50, n_jobs=4, verbosity=0,
                             eval_metric="logloss")


def _lgb_clf():
    import lightgbm as lgb
    return lgb.LGBMClassifier(n_estimators=250, num_leaves=15, learning_rate=0.03, subsample=0.8,
                              subsample_freq=1, colsample_bytree=0.6, min_child_samples=100,
                              n_jobs=4, verbose=-1)


def _gp():
    k = ConstantKernel(1e-4, (1e-8, 1e-1)) * RBF(length_scale=10.0, length_scale_bounds=(1e-1, 1e3)) \
        + WhiteKernel(1e-4, (1e-8, 1e-1))
    return GaussianProcessRegressor(kernel=k, normalize_y=True, n_restarts_optimizer=0, random_state=0)


REGRESSORS: List[Spec] = [
    # naive baselines
    Spec("naive_zero", "Random walk (zero)", "Naive baselines", "naive",
         "Predicts tomorrow's return is exactly zero — the 'prices are a random walk' benchmark."),
    Spec("naive_mean", "Historical mean (drift)", "Naive baselines", "naive",
         "Predicts the long-run average daily return seen so far — THE benchmark every model must beat."),
    Spec("naive_last", "Persistence (last return)", "Naive baselines", "naive",
         "Predicts tomorrow repeats today's move — tests pure momentum."),
    # linear
    Spec("ols", "Linear regression (OLS)", "Linear", "reg",
         "Fits one straight-line weight per feature by least squares — simplest possible model.",
         LinearRegression, fset="fast"),
    Spec("ridge", "Ridge", "Linear", "reg",
         "Linear model that shrinks all weights toward zero to resist over-fitting noise.",
         lambda: Ridge(alpha=50.0), fset="fast"),
    Spec("lasso", "Lasso", "Linear", "reg",
         "Linear model that sets useless features' weights to exactly zero (automatic feature selection).",
         lambda: Lasso(alpha=1e-4, max_iter=5000), fset="fast"),
    Spec("elasticnet", "ElasticNet", "Linear", "reg",
         "Blend of Ridge and Lasso — shrinks weights and drops the weakest features.",
         lambda: ElasticNet(alpha=1e-4, l1_ratio=0.5, max_iter=5000), fset="fast"),
    Spec("huber", "Huber regression", "Linear", "reg",
         "Linear model that down-weights crash/spike days so a few outliers can't dominate the fit.",
         lambda: HuberRegressor(epsilon=1.35, alpha=10.0, max_iter=500), cap=5000, fset="fast", par=True),
    Spec("quantile", "Quantile (median) regression", "Linear", "reg",
         "Fits the MEDIAN next-day return instead of the mean — robust to fat-tailed days.",
         lambda: QuantileRegressor(quantile=0.5, alpha=1e-3, solver="highs"), cap=2000, fset="fast", par=True),
    Spec("theilsen", "Theil–Sen", "Linear", "reg",
         "Robust linear fit built from the median of many small-sample fits.",
         lambda: TheilSenRegressor(max_subpopulation=500, random_state=0),
         cap=3000, fset="core", par=True),
    Spec("pls", "Partial least squares (PLS)", "Linear", "reg",
         "Compresses the ~90 features into 3 hidden factors that best explain returns, then regresses on them.",
         lambda: PLSRegression(n_components=3), fset="fast"),
    # kernel / neighbours
    Spec("linsvr", "Linear SVR", "Kernel & neighbours", "reg",
         "Support-vector regression with a linear kernel — ignores errors inside a small 'tube'.",
         lambda: LinearSVR(epsilon=0.5, C=1e-3, max_iter=5000, dual="auto"), fset="fast", tt=True),
    Spec("svr_rbf", "SVR (RBF kernel)", "Kernel & neighbours", "reg",
         "Support-vector regression with a curved (radial) kernel that can learn non-linear shapes.",
         lambda: SVR(kernel="rbf", C=0.1, epsilon=0.5, gamma="scale"), cap=3000, fset="fast", tt=True, par=True),
    Spec("knn", "K-nearest neighbours", "Kernel & neighbours", "reg",
         "Finds the 100 most similar past days and averages what happened next.",
         lambda: KNeighborsRegressor(n_neighbors=100, weights="uniform"), fset="fast", par=True),
    # trees & boosting
    Spec("tree", "Decision tree", "Trees & boosting", "reg",
         "A single flowchart of if/then splits — easy to read but prone to memorising noise.",
         lambda: DecisionTreeRegressor(max_depth=5, min_samples_leaf=200, random_state=0), scale=False),
    Spec("rf", "Random forest", "Trees & boosting", "reg",
         "Averages 100 decorrelated trees, each grown on a bootstrap sample — robust non-linear model.",
         lambda: RandomForestRegressor(n_estimators=100, max_depth=7, min_samples_leaf=100, max_samples=0.5,
                                       max_features=0.33, n_jobs=4, random_state=0), scale=False),
    Spec("et", "Extra trees", "Trees & boosting", "reg",
         "Like a random forest but with random split points — even more variance reduction.",
         lambda: ExtraTreesRegressor(n_estimators=100, max_depth=7, min_samples_leaf=100,
                                     max_features=0.4, n_jobs=4, random_state=0), scale=False),
    Spec("gbr", "Gradient boosting", "Trees & boosting", "reg",
         "Builds small trees one after another, each correcting the previous trees' errors.",
         lambda: GradientBoostingRegressor(n_estimators=120, max_depth=3, learning_rate=0.03,
                                           subsample=0.7, min_samples_leaf=100, random_state=0),
         cap=6000, scale=False, par=True),
    Spec("hgb", "Histogram gradient boosting", "Trees & boosting", "reg",
         "Fast LightGBM-style boosting built into scikit-learn, with early stopping.",
         lambda: HistGradientBoostingRegressor(max_iter=300, learning_rate=0.03, max_leaf_nodes=15,
                                               min_samples_leaf=100, early_stopping=True, random_state=0),
         scale=False),
    Spec("ada", "AdaBoost", "Trees & boosting", "reg",
         "Boosting that re-weights the days the previous trees got most wrong.",
         lambda: AdaBoostRegressor(DecisionTreeRegressor(max_depth=3, min_samples_leaf=100),
                                   n_estimators=50, learning_rate=0.05, random_state=0),
         cap=6000, scale=False, par=True),
    Spec("xgb", "XGBoost", "Trees & boosting", "reg",
         "Industry-standard regularised gradient boosting (Kaggle workhorse).",
         _xgb_reg, requires="xgboost", scale=False),
    Spec("lgbm", "LightGBM", "Trees & boosting", "reg",
         "Microsoft's leaf-wise gradient boosting — very fast on long histories.",
         _lgb_reg, requires="lightgbm", scale=False),
    Spec("catboost", "CatBoost", "Trees & boosting", "reg",
         "Yandex's ordered boosting with symmetric trees — resistant to target leakage.",
         _cat_reg, requires="catboost", scale=False, cap=12000),
    # neural
    Spec("mlp", "Neural network (MLP)", "Neural", "reg",
         "A 2-layer feed-forward neural network (32→16 neurons) with weight decay and early stopping.",
         lambda: MLPRegressor(hidden_layer_sizes=(32, 16), alpha=1.0, learning_rate_init=1e-3,
                              max_iter=100, early_stopping=True, n_iter_no_change=8, random_state=0),
         cap=8000, fset="fast", tt=True, par=True),
    Spec("gru", "GRU / LSTM sequence net", "Neural", "reg",
         "Recurrent network reading the last 20 days as a sequence.", requires="torch",
         note="reference-only: PyTorch is not installed (multi-GB dependency kept optional)."),
    Spec("cnn1d", "1-D CNN", "Neural", "reg",
         "Convolutional network scanning the last 20 days for local patterns.", requires="torch",
         note="reference-only: PyTorch is not installed (multi-GB dependency kept optional)."),
    # probabilistic
    Spec("bayes_ridge", "Bayesian ridge (with intervals)", "Probabilistic", "reg",
         "Linear model that also outputs an uncertainty band; we check how often reality lands inside it.",
         BayesianRidge, fset="fast"),
    Spec("gp", "Gaussian process", "Probabilistic", "reg",
         "Non-parametric Bayesian model that predicts from similarity to past days, with uncertainty.",
         _gp, cap=1200, fset="fast", par=True),
    # time series
    Spec("arima", "ARIMA(1,0,1)", "Time series", "ts",
         "Classic Box–Jenkins model of returns from their own recent values and shocks.",
         requires="statsmodels", cap=3000, par=True),
    Spec("sarimax", "SARIMAX + astro exogenous", "Time series", "ts",
         "ARIMA(1,0,1) plus planetary drivers (lunar phase, retrogrades, eclipse season, aspects) as outside inputs.",
         requires="statsmodels", cap=3000, par=True),
    Spec("ses", "Exponential smoothing", "Time series", "ts",
         "Forecasts tomorrow as an exponentially-weighted average of past returns (fitted decay).",
         requires="statsmodels", cap=5000),
    Spec("holt_winters", "Holt–Winters (weekly season)", "Time series", "ts",
         "Exponential smoothing with a 5-day weekly seasonal pattern (day-of-week effect).",
         requires="statsmodels", cap=5000),
    Spec("theta", "Theta method", "Time series", "ts",
         "M3-competition winner: half long-run trend line, half smoothed level, applied to log price.",
         cap=5000),
]

SARIMAX_EXOG = ["moon_phase_cos", "moon_phase_sin", "mercury_retro", "eclipse_season",
                "aspect_score_square", "aspect_score_trine"]

CLASSIFIERS: List[Spec] = [
    Spec("logit", "Logistic regression", "Direction classifiers", "clf",
         "Linear model of the odds that the stock closes higher.",
         lambda: LogisticRegression(C=0.01, max_iter=500), fset="fast"),
    Spec("nb", "Naive Bayes", "Direction classifiers", "clf",
         "Treats every feature as independent evidence for 'up' vs 'down'.", GaussianNB, fset="fast"),
    Spec("rf_clf", "Random forest classifier", "Direction classifiers", "clf",
         "100-tree forest voting on up vs down.",
         lambda: RandomForestClassifier(n_estimators=100, max_depth=7, min_samples_leaf=100, max_samples=0.5,
                                        max_features=0.33, n_jobs=4, random_state=0), scale=False),
    Spec("et_clf", "Extra trees classifier", "Direction classifiers", "clf",
         "Extra-randomised trees voting on up vs down.",
         lambda: ExtraTreesClassifier(n_estimators=100, max_depth=7, min_samples_leaf=100,
                                      max_features=0.4, n_jobs=4, random_state=0), scale=False),
    Spec("hgb_clf", "HistGB classifier", "Direction classifiers", "clf",
         "Histogram gradient boosting predicting the probability of an up move.",
         lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.03, max_leaf_nodes=15,
                                                min_samples_leaf=100, early_stopping=True, random_state=0),
         scale=False),
    Spec("xgb_clf", "XGBoost classifier", "Direction classifiers", "clf",
         "XGBoost predicting the probability of an up move.", _xgb_clf, requires="xgboost", scale=False),
    Spec("lgbm_clf", "LightGBM classifier", "Direction classifiers", "clf",
         "LightGBM predicting the probability of an up move.", _lgb_clf, requires="lightgbm", scale=False),
]

FAMILY_ORDER = ["Naive baselines", "Linear", "Kernel & neighbours", "Trees & boosting", "Neural",
                "Probabilistic", "Time series", "Ensembles", "Direction classifiers"]


def catalog() -> List[Dict[str, Any]]:
    out = []
    for s in REGRESSORS + CLASSIFIERS:
        avail = s.requires is None or has_module(s.requires)
        out.append({"key": s.key, "name": s.name, "family": s.family, "kind": s.kind, "desc": s.desc,
                    "cap": s.cap, "available": avail,
                    "status_if_missing": None if avail else (s.note or f"{s.requires} not installed")})
    out.append({"key": "ens_avg", "name": f"Average of top {TOP_K}", "family": "Ensembles", "kind": "ens",
                "desc": f"Simple average of the {TOP_K} best out-of-sample models.", "cap": None,
                "available": True, "status_if_missing": None})
    out.append({"key": "ens_stack", "name": f"Stacked top {TOP_K}", "family": "Ensembles", "kind": "ens",
                "desc": "A non-negative linear blender learns how much to trust each top model, using only earlier folds.",
                "cap": None, "available": True, "status_if_missing": None})
    return out


# ---------------------------------------------------------------------------
# Walk-forward folds
# ---------------------------------------------------------------------------
def make_folds(n: int, n_folds: int = N_FOLDS, gap: int = 0, min_train: int = 750) -> List[tuple]:
    """Expanding-window folds over the most recent part of history.

    Each test block is ~10 years (2,520 sessions) or less for short histories."""
    test = min(2520, max(60, (n - min_train) // n_folds))
    folds = []
    for i in range(n_folds):
        te_end = n - (n_folds - 1 - i) * test
        te_start = te_end - test
        tr_end = te_start - gap
        if tr_end < min(min_train, n // 3):
            continue
        folds.append((np.arange(0, tr_end), np.arange(te_start, te_end)))
    return folds


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def reg_metrics(y: np.ndarray, p: np.ndarray, bench: np.ndarray) -> Dict[str, Optional[float]]:
    e = y - p
    eb = y - bench
    sse, sseb = float(np.sum(e ** 2)), float(np.sum(eb ** 2))
    r2_os = 1.0 - sse / sseb if sseb > 0 else 0.0
    nz = (y != 0) & (p != 0)
    hit = float(np.mean(np.sign(p[nz]) == np.sign(y[nz]))) if nz.sum() > 0.5 * len(y) else None
    ic = float(stats.spearmanr(p, y).statistic) if np.std(p) > 0 else 0.0
    d = eb ** 2 - e ** 2
    dm = float(np.mean(d) / (np.std(d, ddof=1) / np.sqrt(len(d)))) if np.std(d) > 0 else 0.0
    return {"r2_os": _f(r2_os), "rmse": _f(np.sqrt(np.mean(e ** 2)), 7), "mae": _f(np.mean(np.abs(e)), 7),
            "hit_rate": _f(hit, 4), "ic": _f(ic, 4), "dm_t": _f(dm, 3)}


# ---------------------------------------------------------------------------
# Time-series model predictors (one-step-ahead over the test block)
# ---------------------------------------------------------------------------
def _ts_predict(spec: Spec, df: pd.DataFrame, y: np.ndarray, tr: np.ndarray, te: np.ndarray) -> np.ndarray:
    tr = tr[-spec.cap:] if spec.cap else tr
    ytr, yte = y[tr], y[te]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if spec.key in ("arima", "sarimax"):
            from statsmodels.tsa.statespace.sarimax import SARIMAX
            ex_tr = ex_te = None
            if spec.key == "sarimax":
                cols = [c for c in SARIMAX_EXOG if c in df.columns]
                ex = df[cols].values.astype(float)
                mu, sd = ex[tr].mean(0), ex[tr].std(0) + 1e-9
                ex_tr, ex_te = (ex[tr] - mu) / sd, (ex[te] - mu) / sd
            m = SARIMAX(ytr, exog=ex_tr, order=(1, 0, 1), trend="c")
            res = m.fit(disp=False, maxiter=60)
            # continue filtering through train+test with fixed params → one-step-ahead forecasts
            full_y = np.concatenate([ytr, yte])
            full_x = None if ex_tr is None else np.vstack([ex_tr, ex_te])
            res2 = res.apply(full_y, exog=full_x)
            return np.asarray(res2.predict())[len(ytr):]
        if spec.key == "ses":
            from statsmodels.tsa.holtwinters import SimpleExpSmoothing
            alpha = float(SimpleExpSmoothing(ytr, initialization_method="estimated").fit().params["smoothing_level"])
            alpha = min(max(alpha, 1e-3), 0.999)
            full = np.concatenate([ytr, yte])
            lvl = pd.Series(full).ewm(alpha=alpha, adjust=False).mean().values
            return lvl[len(ytr) - 1:-1]
        if spec.key == "holt_winters":
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            fit = ExponentialSmoothing(ytr, seasonal="add", seasonal_periods=5,
                                       initialization_method="estimated").fit()
            a = float(fit.params["smoothing_level"])
            g = float(fit.params.get("smoothing_seasonal", 0.0) or 0.0)
            level = float(fit.level[-1])
            season = list(np.asarray(fit.season)[-5:])
            preds = np.empty(len(yte))
            for k, obs in enumerate(yte):
                s = season[-5]
                preds[k] = level + s
                new_level = a * (obs - s) + (1 - a) * level
                season.append(g * (obs - level) + (1 - g) * s)
                level = new_level
            return preds
        if spec.key == "theta":
            # Hyndman–Billah form of the Theta method on log price:
            # forecast(t) = SES level(t-1) + b0 / (2·alpha), b0 = linear-trend slope of the train window
            logp = np.log(df["close"].values.astype(float))
            ptr = logp[tr]
            b = float(np.polyfit(np.arange(len(ptr)), ptr, 1)[0])
            alpha = 0.9
            try:
                from statsmodels.tsa.holtwinters import SimpleExpSmoothing
                alpha = float(SimpleExpSmoothing(ptr, initialization_method="estimated").fit().params["smoothing_level"])
            except Exception:
                pass
            alpha = min(max(alpha, 0.05), 1.0)
            full = logp[tr[0]:te[-1] + 1]
            lvl = pd.Series(full).ewm(alpha=alpha, adjust=False).mean().values
            off = te[0] - tr[0]
            prev_lvl = lvl[off - 1:off - 1 + len(te)]
            prev_p = full[off - 1:off - 1 + len(te)]
            return np.expm1(prev_lvl + b / (2 * alpha) - prev_p)
    raise ValueError(spec.key)


# ---------------------------------------------------------------------------
class ModelZoo:
    def __init__(self, df: pd.DataFrame, progress: Optional[Callable[[str, int, int], None]] = None,
                 n_jobs: int = 4):
        self.df_all = df
        self.feats = feature_columns(df)
        self.df = df.iloc[:-1].copy()  # drop the future row for training
        self.df = self.df[np.isfinite(self.df["y1"].values)]
        self.X = self.df[self.feats].values.astype(float)
        self.y = self.df["y1"].values.astype(float)
        self.n = len(self.y)
        self.folds = make_folds(self.n)
        self.test_idx = np.concatenate([te for _, te in self.folds]) if self.folds else np.array([], int)
        self.progress = progress or (lambda *_: None)
        self.n_jobs = n_jobs
        self.oos: Dict[str, np.ndarray] = {}
        self.fold_models: Dict[str, Any] = {}
        self.timings: Dict[str, float] = {}

    def Xs(self, fset: str) -> np.ndarray:
        cols = select_cols(self.feats, fset)
        return self.X if len(cols) == len(self.feats) else self.X[:, cols]

    def _parallel(self, fn, jobs):
        """Run fold jobs in worker processes; fall back to serial if that fails."""
        if self.n_jobs > 1 and len(jobs) > 1:
            try:
                from joblib import Parallel, delayed
                return Parallel(n_jobs=min(self.n_jobs, len(jobs)), backend="loky")(delayed(fn)(*a) for a in jobs)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"parallel folds failed, running serially: {exc}")
        return [fn(*a) for a in jobs]

    # ---------------- regression -----------------
    def _naive(self, key: str, tr: np.ndarray, te: np.ndarray) -> np.ndarray:
        if key == "naive_zero":
            return np.zeros(len(te))
        if key == "naive_mean":
            # expanding historical mean, updated daily (uses only past returns)
            cs = np.cumsum(self.y)
            return cs[te - 1] / te
        if key == "naive_last":
            return self.y[te - 1]
        raise ValueError(key)

    def _spec_fold_preds(self, spec: Spec) -> List[np.ndarray]:
        if spec.kind == "naive":
            return [self._naive(spec.key, tr, te) for tr, te in self.folds]
        if spec.kind == "ts":
            jobs = [(spec, self.df, self.y, tr, te) for tr, te in self.folds]
            return self._parallel(_ts_predict, jobs) if spec.par else [_ts_predict(*j) for j in jobs]
        X = self.Xs(spec.fset)
        if spec.par:
            return self._parallel(_fold_job, [(spec, X, self.y, tr, te) for tr, te in self.folds])
        preds = []
        for fi, (tr, te) in enumerate(self.folds):
            trc = tr[-spec.cap:] if spec.cap else tr
            mdl = build_model(spec)
            mdl.fit(X[trc], self.y[trc])
            preds.append(np.asarray(mdl.predict(X[te])).ravel())
            if fi == len(self.folds) - 1:
                self.fold_models[spec.key] = mdl
        return preds

    def run_regressors(self, done_offset: int, total: int) -> List[Dict[str, Any]]:
        rows = []
        bench = np.concatenate([self._naive("naive_mean", tr, te) for tr, te in self.folds])
        yt = self.y[self.test_idx]
        for i, spec in enumerate(REGRESSORS):
            self.progress(f"{spec.name}", done_offset + i, total)
            row: Dict[str, Any] = {"key": spec.key, "name": spec.name, "family": spec.family, "kind": spec.kind,
                                   "desc": spec.desc, "cap": spec.cap,
                                   "features_used": FSET_LABEL.get(spec.fset) if spec.kind == "reg" else
                                   ("returns + 6 astro inputs" if spec.key == "sarimax" else
                                    "price/returns only" if spec.kind in ("ts", "naive") else None)}
            if spec.requires and not has_module(spec.requires):
                row.update(status="skipped", reason=spec.note or f"{spec.requires} not installed")
                rows.append(row)
                continue
            t0 = time.time()
            try:
                preds = [np.nan_to_num(np.asarray(p, float), nan=0.0, posinf=0.0, neginf=0.0)
                         for p in self._spec_fold_preds(spec)]
                fold_r2 = []
                for (tr, te), p in zip(self.folds, preds):
                    b = self._naive("naive_mean", tr, te)
                    yy = self.y[te]
                    fold_r2.append(1 - np.sum((yy - p) ** 2) / max(np.sum((yy - b) ** 2), 1e-18))
                pred = np.concatenate(preds)
                self.oos[spec.key] = pred
                m = reg_metrics(yt, pred, bench)
                row.update(status="ok", **m, folds_r2_os=[_f(v) for v in fold_r2],
                           folds_beat=int(sum(1 for v in fold_r2 if v > 0)), n_folds=len(fold_r2))
                if spec.key == "bayes_ridge" and spec.key in self.fold_models:
                    mdl = self.fold_models[spec.key]
                    te = self.folds[-1][1]
                    Xb = self.Xs(spec.fset)[te]
                    _, sd = mdl[-1].predict(mdl[:-1].transform(Xb), return_std=True)
                    row["interval90_coverage"] = _f(np.mean(np.abs(self.y[te] - preds[-1]) <= 1.645 * sd), 4)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"zoo model {spec.key} failed: {exc}")
                row.update(status="failed", reason=str(exc)[:160])
            self.timings[spec.key] = round(time.time() - t0, 2)
            row["seconds"] = self.timings[spec.key]
            rows.append(row)
        return rows

    # ---------------- ensembles -----------------
    def run_ensembles(self, rows: List[Dict[str, Any]]) -> tuple:
        bench = np.concatenate([self._naive("naive_mean", tr, te) for tr, te in self.folds])
        yt = self.y[self.test_idx]
        cands = [r for r in rows if r.get("status") == "ok" and r["kind"] == "reg"]
        cands.sort(key=lambda r: r["r2_os"] if r["r2_os"] is not None else -9, reverse=True)
        members = [r["key"] for r in cands[:TOP_K]]
        out: List[Dict[str, Any]] = []
        if len(members) < 2:
            return out, members
        P = np.column_stack([self.oos[k] for k in members])
        avg = P.mean(1)
        self.oos["ens_avg"] = avg
        out.append({"key": "ens_avg", "name": f"Average of top {len(members)}", "family": "Ensembles",
                    "kind": "ens", "desc": f"Simple average of the {len(members)} best feature-based models.",
                    "cap": None, "status": "ok", **reg_metrics(yt, avg, bench), "members": members,
                    "features_used": "member models' inputs"})
        # stacking: blender for fold i learned only on folds < i
        bounds = np.cumsum([0] + [len(te) for _, te in self.folds])
        stack = np.full(len(yt), np.nan)
        weights = None
        for i in range(1, len(self.folds)):
            a, b = bounds[i], bounds[i + 1]
            lr = LinearRegression(positive=True).fit(P[:a], yt[:a])
            stack[a:b] = lr.predict(P[a:b])
            weights = lr.coef_
        ok = np.isfinite(stack)
        if ok.sum() > 50:
            self.oos["ens_stack"] = np.where(ok, stack, avg)
            m = reg_metrics(yt[ok], stack[ok], bench[ok])
            out.append({"key": "ens_stack", "name": f"Stacked top {len(members)}", "family": "Ensembles",
                        "kind": "ens",
                        "desc": "Non-negative linear blend of the top models, weights learned on earlier folds only.",
                        "cap": None, "status": "ok", **m, "members": members,
                        "weights": {k: _f(w, 4) for k, w in zip(members, weights if weights is not None else [])},
                        "features_used": "member models' out-of-sample predictions",
                        "note": "scored on folds 2–5 (fold 1 is needed to learn the first blend)"})
        return out, members

    # ---------------- classifiers -----------------
    def run_classifiers(self, horizon: int, done_offset: int, total: int) -> List[Dict[str, Any]]:
        col = "y1" if horizon == 1 else f"y{horizon}"
        yv = self.df[col].values.astype(float)
        good = np.isfinite(yv)
        yb = (yv[good] > 0).astype(int)
        folds = make_folds(len(yb), gap=horizon - 1)
        rows = []
        for i, spec in enumerate(CLASSIFIERS):
            self.progress(f"{spec.name} ({horizon}d direction)", done_offset + i, total)
            row = {"key": spec.key, "name": spec.name, "family": spec.family, "kind": "clf",
                   "desc": spec.desc, "horizon": horizon, "features_used": FSET_LABEL.get(spec.fset)}
            if spec.requires and not has_module(spec.requires):
                row.update(status="skipped", reason=f"{spec.requires} not installed")
                rows.append(row)
                continue
            t0 = time.time()
            try:
                X = self.Xs(spec.fset)[good]
                jobs = [(spec, X, yb, tr, te) for tr, te in folds]
                probs = self._parallel(_fold_job, jobs) if spec.par else [_fold_job(*j) for j in jobs]
                ys = [yb[te] for _, te in folds]
                base_acc = [np.mean(yb[te] == int(yb[tr].mean() >= 0.5)) for tr, te in folds]
                pr, yy = np.concatenate(probs), np.concatenate(ys)
                pred = (pr >= 0.5).astype(int)
                auc = roc_auc_score(yy, pr) if len(np.unique(yy)) > 1 else 0.5
                self.oos[f"{spec.key}_{horizon}"] = pr
                acc = accuracy_score(yy, pred)
                row.update(status="ok", accuracy=_f(acc, 4),
                           balanced_accuracy=_f(balanced_accuracy_score(yy, pred), 4), auc=_f(auc, 4),
                           base_rate=_f(np.mean(base_acc), 4), up_share=_f(yy.mean(), 4),
                           edge_vs_base=_f(acc - np.mean(base_acc), 4))
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"classifier {spec.key} failed: {exc}")
                row.update(status="failed", reason=str(exc)[:160])
            row["seconds"] = round(time.time() - t0, 2)
            rows.append(row)
        return rows

    # ---------------- importance -----------------
    def importance(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        spec_by = {s.key: s for s in REGRESSORS}
        cands = [r for r in rows if r.get("status") == "ok" and r["kind"] == "reg"
                 and r["key"] in self.fold_models and spec_by[r["key"]].fset == "all"]
        cands.sort(key=lambda r: r["r2_os"] or -9, reverse=True)
        if not cands:
            return {"model": None, "features": []}
        key = cands[0]["key"]
        mdl = self.fold_models[key]
        te = self.folds[-1][1]
        te = te[-2000:]
        pi = permutation_importance(mdl, self.X[te], self.y[te], n_repeats=4, random_state=0,
                                    scoring="neg_mean_squared_error", n_jobs=1)
        base = float(np.mean(self.y[te] ** 2)) or 1.0
        imp = pi.importances_mean / base * 100
        sd = pi.importances_std / base * 100
        est = mdl[-1] if hasattr(mdl, "steps") else mdl
        native = np.asarray(getattr(est, "feature_importances_", np.zeros(len(self.feats))), float)
        if native.sum() > 0:
            native = native / native.sum()
        order = np.argsort(-imp)
        feats = []
        for j in order[:15]:
            nm = self.feats[j]
            feats.append({"feature": nm, "group": feature_group(nm), "meaning": feature_meaning(nm),
                          "importance": _f(imp[j], 5), "importance_sd": _f(sd[j], 5),
                          "native_share": _f(native[j], 5) if native.sum() > 0 else None,
                          "real": bool(imp[j] > 2 * sd[j] and imp[j] > 0)})
        pos = np.clip(imp, 0, None)
        tot = float(pos.sum()) or 1.0
        grp: Dict[str, float] = {}
        for j, nm in enumerate(self.feats):
            grp[feature_group(nm)] = grp.get(feature_group(nm), 0.0) + float(pos[j]) / tot
        return {"model": key, "model_name": spec_by[key].name,
                "method": "permutation importance on the last out-of-sample block (2,000 sessions, 4 shuffles)",
                "unit": "% increase in out-of-sample squared error when the feature is shuffled",
                "features": feats, "group_share": {k: _f(v, 4) for k, v in grp.items()},
                "n_real": int(sum(1 for f in feats if f["real"]))}

    # ---------------- final fits + forecast -----------------
    def forecast(self, members: List[str], clf_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        spec_by = {s.key: s for s in REGRESSORS + CLASSIFIERS}
        Xall = self.df_all[self.feats].values.astype(float)
        next_date = str(self.df_all.index[-1].date())
        last_close = float(self.df["close"].values[-1])
        out: Dict[str, Any] = {"next_session": next_date, "last_close": _f(last_close, 4), "horizons": []}
        feat_members = [k for k in members if spec_by.get(k) and spec_by[k].kind == "reg"]
        recent = self.df.iloc[-2520:]
        for h in (1, 5, 20):
            col = "y1" if h == 1 else f"y{h}"
            yv = self.df[col].values.astype(float)
            good = np.isfinite(yv)
            yh = yv[good]
            yh_lr = np.log1p(yh) if h == 1 else yh
            preds = []
            for k in feat_members:
                s = spec_by[k]
                try:
                    cols = select_cols(self.feats, s.fset)
                    Xh = self.X[good][:, cols]
                    trc = np.arange(len(yh))[-s.cap:] if s.cap else np.arange(len(yh))
                    mdl = build_model(s)
                    mdl.fit(Xh[trc], yh_lr[trc])
                    preds.append(float(np.ravel(mdl.predict(Xall[-1:, cols]))[0]))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"forecast fit {k} h={h} failed: {exc}")
            if not preds:
                preds = [float(np.nanmean(yh_lr))]
            mu = float(np.mean(preds))
            hist = recent[col].values.astype(float)
            hist = np.log1p(hist) if h == 1 else hist
            hist = hist[np.isfinite(hist)]
            dev = hist - hist.mean()
            lo, hi = np.percentile(dev, 5), np.percentile(dev, 95)
            sd = float(np.std(hist)) or 1e-9
            entry: Dict[str, Any] = {
                "horizon": h, "expected_return_pct": _f(np.expm1(mu) * 100, 3),
                "band_low_pct": _f(np.expm1(mu + lo) * 100, 3), "band_high_pct": _f(np.expm1(mu + hi) * 100, 3),
                "expected_price": _f(last_close * np.exp(mu), 4),
                "price_low": _f(last_close * np.exp(mu + lo), 4), "price_high": _f(last_close * np.exp(mu + hi), 4),
                "member_forecasts_pct": [_f(np.expm1(p) * 100, 3) for p in preds],
                "p_up": _f(stats.norm.cdf(mu / sd), 4), "p_up_source": "ensemble mean vs 10-year volatility (normal approx.)",
                "hist_up_share": _f(np.mean(hist > 0), 4)}
            ok = [r for r in clf_rows if r.get("status") == "ok" and r.get("horizon") == h]
            if ok:
                best = max(ok, key=lambda r: r["auc"] or 0)
                probs = []
                yb = (yh > 0).astype(int)
                trc = np.arange(len(yb))[-6000:]  # recent ~24y keeps the final fits quick
                for r in ok:
                    s = spec_by[r["key"]]
                    try:
                        cols = select_cols(self.feats, s.fset)
                        mdl = build_model(s)
                        mdl.fit(self.X[good][:, cols][trc], yb[trc])
                        probs.append((r["key"], float(mdl.predict_proba(Xall[-1:, cols])[0, 1])))
                    except Exception:  # noqa: BLE001
                        pass
                if probs:
                    entry["p_up"] = _f(np.mean([p for _, p in probs]), 4)
                    entry["p_up_source"] = f"average of {len(probs)} direction classifiers"
                    entry["p_up_best"] = _f(dict(probs).get(best["key"], np.nan), 4)
                    entry["best_classifier"] = best["name"]
            out["horizons"].append(entry)
        out["members"] = feat_members
        out["band_method"] = ("90% band = the stock's own 5th–95th percentile move over the last 10 years, "
                              "centred on the ensemble forecast")
        return out

    # ---------------- predicted vs actual -----------------
    def pred_vs_actual(self, key: str) -> Dict[str, Any]:
        if key not in self.oos:
            return {}
        p = self.oos[key]
        yt = self.y[self.test_idx]
        dates = self.df.index[self.test_idx]
        last = slice(-250, None)
        series = [{"date": str(d.date()), "actual": _f(a * 100, 4), "predicted": _f(b * 100, 4)}
                  for d, a, b in zip(dates[last], yt[last], p[last])]
        q = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False).values
        cal = []
        for d in range(10):
            m = q == d
            if m.any():
                cal.append({"decile": d + 1, "avg_predicted": _f(p[m].mean() * 100, 4),
                            "avg_actual": _f(yt[m].mean() * 100, 4), "up_share": _f((yt[m] > 0).mean(), 4)})
        corr = float(np.corrcoef(p, yt)[0, 1]) if np.std(p) > 0 else 0.0
        return {"model": key, "series": series, "deciles": cal, "corr": _f(corr, 4)}


# ---------------------------------------------------------------------------
# Plain-English insights
# ---------------------------------------------------------------------------
def _pct(v: Optional[float], nd: int = 2) -> str:
    return "n/a" if v is None else f"{v * 100:.{nd}f}%"


def model_insight(r: Dict[str, Any], naive_hit: Optional[float]) -> str:
    if r.get("status") != "ok":
        return f"Not run — {r.get('reason', 'unavailable')}."
    if r["key"] == "naive_mean":
        return ("This IS the benchmark (R²_OS = 0 by definition): every other model must beat simply assuming "
                f"the average return so far; it guessed the sign right {_pct(r.get('hit_rate'), 1)} of days.")
    if r["kind"] == "clf":
        edge = r.get("edge_vs_base") or 0
        verdict = ("a small edge over" if edge > 0.005 else "no better than" if edge > -0.005 else "worse than")
        return (f"Called the {r['horizon']}-day direction right {_pct(r['accuracy'], 1)} of the time vs "
                f"{_pct(r['base_rate'], 1)} for always guessing the majority — {verdict} the base rate "
                f"(AUC {r['auc']:.3f}; 0.5 = coin flip).")
    r2 = r.get("r2_os") or 0.0
    fb, nf = r.get("folds_beat"), r.get("n_folds")
    beat = "beat" if r2 > 0 else "did not beat"
    folds = f" (won in {fb} of {nf} decade-long test blocks)" if fb is not None else ""
    hit = r.get("hit_rate")
    hit_s = f"; it guessed the sign right {_pct(hit, 1)} of days" if hit is not None else ""
    sig = ""
    if r.get("dm_t") is not None and r2 > 0:
        sig = " — statistically meaningful" if r["dm_t"] > 2 else " — but the gain is within noise"
    extra = ""
    if r.get("interval90_coverage") is not None:
        extra = f" Its 90% band contained {_pct(r['interval90_coverage'], 0)} of outcomes."
    return f"{r['name']} {beat} the historical-mean forecast out of sample (R²_OS {r2 * 100:+.3f}%){folds}{hit_s}{sig}.{extra}"


def build_insights(reg_rows, ens_rows, clf_rows, imp, fc, meta) -> Dict[str, Any]:
    ok = [r for r in reg_rows + ens_rows if r.get("status") == "ok" and r["kind"] != "naive"]
    ok.sort(key=lambda r: r["r2_os"] or -9, reverse=True)
    best = ok[0] if ok else None
    beaters = [r for r in ok if (r["r2_os"] or 0) > 0]
    sig = [r for r in beaters if (r.get("dm_t") or 0) > 2]
    fams: Dict[str, List[float]] = {}
    for r in ok:
        fams.setdefault(r["family"], []).append(r["r2_os"] or 0)
    fam_best = max(fams.items(), key=lambda kv: max(kv[1])) if fams else None

    lines: List[str] = []
    if best and not beaters:
        lines.append(
            f"No model beat the naive historical-mean forecast on {meta['oos_days']:,} unseen sessions "
            f"({meta['oos_years']} years); the closest was {best['name']} ({best['family']}) at R²_OS "
            f"{best['r2_os'] * 100:+.3f}%.")
    elif best:
        lines.append(
            f"Winner: {best['name']} ({best['family']}) with R²_OS {best['r2_os'] * 100:+.3f}% versus the naive "
            f"historical-mean forecast, tested on {meta['oos_days']:,} unseen sessions ({meta['oos_years']} years).")
    if best and not beaters:
        lines.append("None of the models beat the naive forecast out of sample. For this stock, planetary and "
                     "technical features did not improve on simply assuming the average return — that is the "
                     "normal, honest outcome for daily returns.")
    elif not sig:
        lines.append(f"{len(beaters)} of {len(ok)} models edged past the naive forecast, but none by a statistically "
                     "meaningful margin (DM t-stat < 2) — treat the ranking as a weak preference, not proof.")
    else:
        lines.append(f"{len(sig)} model(s) beat the naive forecast with a DM t-stat above 2 "
                     f"({', '.join(r['name'] for r in sig[:3])}) — a small but real out-of-sample edge on this history.")
    if fam_best:
        lines.append(f"Best family: {fam_best[0]}. "
                     + ("Non-linear tree models leading suggests any signal is in interactions/regimes rather than straight lines."
                        if fam_best[0] == "Trees & boosting" else
                        "Simple linear models leading means the complex models mostly fitted noise — prefer simple."
                        if fam_best[0] == "Linear" else
                        "Combining models helped — diversification across models reduces error."
                        if fam_best[0] == "Ensembles" else
                        "Return-only time-series models leading means the extra features added little."
                        if fam_best[0] == "Time series" else ""))
    clf_ok = [r for r in clf_rows if r.get("status") == "ok"]
    direction: List[str] = []
    for h in (1, 5):
        rows = [r for r in clf_ok if r["horizon"] == h]
        if rows:
            b = max(rows, key=lambda r: r["auc"] or 0)
            edge = (b["accuracy"] or 0) - (b["base_rate"] or 0)
            direction.append(
                f"{h}-day direction: best is {b['name']} with AUC {b['auc']:.3f} and accuracy {_pct(b['accuracy'], 1)} "
                f"vs {_pct(b['base_rate'], 1)} from always guessing '{'up' if (b['up_share'] or 0.5) >= 0.5 else 'down'}' "
                + ("— a modest edge." if edge > 0.01 and (b["auc"] or 0) > 0.52 else "— essentially a coin flip beyond the base rate."))
    feat_lines: List[str] = []
    if imp.get("features"):
        top = imp["features"][:3]
        gs = imp.get("group_share") or {}
        feat_lines.append(
            f"What {imp.get('model_name', imp['model'])} leaned on most out of sample: "
            + "; ".join(f"{f['feature']} ({f['meaning']})" for f in top) + ".")
        astro_top = [f for f in imp["features"] if f["group"] == "astro" and f["real"]]
        feat_lines.append(
            f"Of the error reduction that features provide, technical inputs account for {_pct(gs.get('technical'), 0)}, "
            f"astro inputs {_pct(gs.get('astro'), 0)} and calendar {_pct(gs.get('calendar'), 0)}. "
            f"Only {imp.get('n_real', 0)} of the top 15 features clear the noise bar (importance > 2× its shuffle spread)"
            + (f"; the strongest astro one is {astro_top[0]['feature']} — {astro_top[0]['meaning']}." if astro_top else
               "; no astro feature clears it on this history."))
    fc_lines: List[str] = []
    for hz in fc.get("horizons", []):
        fc_lines.append(
            f"Next {hz['horizon']} session{'s' if hz['horizon'] > 1 else ''}: ensemble expects "
            f"{hz['expected_return_pct']:+.2f}% (90% band {hz['band_low_pct']:+.1f}% to {hz['band_high_pct']:+.1f}%), "
            f"P(up) {_pct(hz['p_up'], 0)} vs {_pct(hz['hist_up_share'], 0)} historically.")
    # what to do
    best_r2 = (best or {}).get("r2_os") or 0
    h1 = next((h for h in fc.get("horizons", []) if h["horizon"] == 1), None)
    tilt = ""
    if h1:
        diff = (h1["p_up"] or 0.5) - (h1["hist_up_share"] or 0.5)
        tilt = ("slightly more bullish than usual" if diff > 0.02 else
                "slightly more bearish than usual" if diff < -0.02 else "in line with the stock's normal odds")
    if sig:
        todo = (f"There is a measurable but small edge. Use the ensemble as a TILT: lean {tilt or 'with the forecast'}, "
                "keep position size small (e.g. ≤ 1/4 of normal), and re-run monthly — edges like this decay.")
    elif beaters:
        todo = (f"Edge is within noise. Treat today's reading ({tilt}) as context only; let your core plan, risk limits "
                "and diversification drive decisions. Do not trade it as a signal.")
    else:
        todo = ("No model beats naive, so the honest action is: don't trade these forecasts. Use buy-and-hold or your "
                "existing strategy, and treat the astro features as a curiosity, not a signal.")
    return {"headline": lines[0] if lines else "No models trained.", "overall": lines, "direction": direction,
            "features": feat_lines, "forecast": fc_lines, "what_to_do": todo,
            "beats_naive": bool(beaters), "significant": bool(sig), "best_model": (best or {}).get("key")}


# ---------------------------------------------------------------------------
def run_zoo(df: pd.DataFrame, symbol: str, vedic: bool,
            progress: Optional[Callable[[str, int, int], None]] = None) -> Dict[str, Any]:
    t_start = time.time()
    zoo = ModelZoo(df, progress)
    if zoo.n < 300 or not zoo.folds:
        raise ValueError(f"not enough history ({zoo.n} sessions) for walk-forward validation")
    total = len(REGRESSORS) + 2 * len(CLASSIFIERS) + 3
    reg_rows = zoo.run_regressors(0, total)
    ens_rows, members = zoo.run_ensembles(reg_rows)
    clf_rows = zoo.run_classifiers(1, len(REGRESSORS), total) + zoo.run_classifiers(5, len(REGRESSORS) + len(CLASSIFIERS), total)
    zoo.progress("feature importance", total - 3, total)
    imp = zoo.importance(reg_rows)
    zoo.progress("ensemble forecast (final fits on full history)", total - 2, total)
    fc = zoo.forecast(members, clf_rows)
    all_reg = reg_rows + ens_rows
    best = max([r for r in all_reg if r.get("status") == "ok" and r["kind"] != "naive"],
               key=lambda r: r["r2_os"] or -9, default=None)
    pva = zoo.pred_vs_actual("ens_avg" if "ens_avg" in zoo.oos else (best or {}).get("key", "naive_mean"))
    idx = zoo.df.index
    ti = zoo.test_idx
    meta = {"rows": int(zoo.n), "start": str(idx[0].date()), "end": str(idx[-1].date()),
            "years": round((idx[-1] - idx[0]).days / 365.2425, 1), "features": len(zoo.feats),
            "oos_days": int(len(ti)), "oos_start": str(idx[ti[0]].date()),
            "oos_years": round((idx[ti[-1]] - idx[ti[0]]).days / 365.2425, 1), "folds": len(zoo.folds),
            "fold_ranges": [{"train_end": str(idx[tr[-1]].date()), "test_start": str(idx[te[0]].date()),
                             "test_end": str(idx[te[-1]].date())} for tr, te in zoo.folds]}
    naive_hit = next((r.get("hit_rate") for r in reg_rows if r["key"] == "naive_mean"), None)
    for r in all_reg + clf_rows:
        r["insight"] = model_insight(r, naive_hit)
    insights = build_insights(reg_rows, ens_rows, clf_rows, imp, fc, meta)
    caps = sorted({(s.name, s.cap) for s in REGRESSORS + CLASSIFIERS if s.cap}, key=lambda t: t[1])
    result = {
        "success": True, "symbol": symbol, "vedic": vedic, "zodiac": "sidereal (Lahiri)" if vedic else "tropical",
        "data": meta,
        "leaderboard": sorted([r for r in all_reg if r.get("status") == "ok"], key=lambda r: r["r2_os"] or -9, reverse=True)
        + [r for r in all_reg if r.get("status") != "ok"],
        "classifiers": clf_rows,
        "best_model": (best or {}).get("key"), "best_name": (best or {}).get("name"),
        "ensemble_members": members,
        "feature_importance": imp, "pred_vs_actual": pva, "forecast": fc, "insights": insights,
        "families": FAMILY_ORDER,
        "caps": [{"model": n, "max_train_rows": c} for n, c in caps]
        + [{"model": "Direction classifiers (final forecast fit)", "max_train_rows": 6000}],
        "method": ("Expanding-window walk-forward CV: 5 test blocks of up to 10 years each at the end of history; "
                   "each model is trained only on sessions before its test block. Technical features use data up to "
                   "the previous close; planetary features are computed for the session date (known in advance)."),
        "counts": {"trained": sum(1 for r in all_reg + clf_rows if r.get("status") == "ok"),
                   "skipped": sum(1 for r in all_reg + clf_rows if r.get("status") == "skipped"),
                   "failed": sum(1 for r in all_reg + clf_rows if r.get("status") == "failed")},
        "runtime_seconds": round(time.time() - t_start, 1),
        "disclaimer": "Educational research only — not financial advice. Past out-of-sample results do not guarantee future performance.",
    }
    zoo.progress("done", total, total)
    return {"result": result, "oos": {k: v for k, v in zoo.oos.items()}, "test_idx": zoo.test_idx,
            "dates": zoo.df.index, "y": zoo.y}
