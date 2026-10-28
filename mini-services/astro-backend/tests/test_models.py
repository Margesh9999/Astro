"""v1.3 Model Lab: feature engineering, model zoo and backtest on a small demo subset."""
import json
import os

os.environ.setdefault("ASTRO_DEMO_DATA", "1")

import numpy as np
import pytest

from app.services.market_data import synthetic_history
from app.services.model_features import build_dataset, feature_columns, feature_meaning
from app.services import model_zoo as mz


@pytest.fixture(scope="module")
def demo_df():
    px = synthetic_history("^NSEI", "max").iloc[-1500:]
    return build_dataset(px, vedic=True)


def test_features_have_no_lookahead_and_future_row(demo_df):
    feats = feature_columns(demo_df)
    assert len(feats) > 60
    for f in ("moon_nakshatra", "tithi", "mercury_retro", "eclipse_season", "aspect_score_square", "rsi_14"):
        assert f in feats
    # last row is the next (unknown) session; its target is NaN, features are finite
    assert np.isnan(demo_df["y1"].iloc[-1])
    assert np.isfinite(demo_df[feats].values).all()
    # ret_lag1 on day t equals the realised return of day t-1
    assert np.allclose(demo_df["ret_lag1"].values[2:-1], demo_df["y1"].values[1:-2], equal_nan=True)
    assert 1 <= demo_df["tithi"].min() and demo_df["tithi"].max() <= 30
    assert all(feature_meaning(f) for f in feats)


def test_zoo_runs_and_every_model_is_scored_or_skipped(demo_df):
    out = mz.run_zoo(demo_df, "^NSEI", True)
    res = out["result"]
    rows = res["leaderboard"] + res["classifiers"]
    keys = {r["key"] for r in res["leaderboard"]}
    assert {"ols", "ridge", "rf", "hgb", "arima", "theta", "naive_mean", "ens_avg"} <= keys
    for r in rows:
        assert r["status"] in ("ok", "skipped", "failed")
        if r["status"] == "ok":
            metric = r.get("r2_os") if r["kind"] != "clf" else r.get("auc")
            assert metric is not None and np.isfinite(metric), r["key"]
        else:
            assert r.get("reason"), r["key"]
        assert r.get("insight")
    assert res["counts"]["failed"] == 0
    assert len(res["forecast"]["horizons"]) == 3
    assert res["insights"]["what_to_do"]
    assert res["data"]["rows"] > 1000
    # JSON-clean (no NaN/Inf)
    json.dumps(res, allow_nan=False)


def test_backtest_endpoint_quick_path():
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/v1/models/backtest", json={"symbol": "^NSEI", "use_vedic": True, "model": "ens_avg"})
    assert r.status_code == 200
    d = r.json()
    assert d["equity_curve"] and d["verdict"]
    assert "strategy" in d and "buy_hold" in d
    json.dumps(d, allow_nan=False)
    assert c.get("/api/v1/models/zoo/catalog").json()["count"] >= 40
