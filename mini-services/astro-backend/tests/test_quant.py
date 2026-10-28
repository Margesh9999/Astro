"""v1.3 Quant Desk tests: signal board, heatmaps, regime, portfolio, forecast, concepts."""
import json
import os

os.environ.setdefault("ASTRO_DEMO_DATA", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.market_data import synthetic_history  # noqa: E402
from app.services.quant_common import BENCH_NAMES, clean  # noqa: E402
from app.services.quant_signals import STRATEGIES, build_signals  # noqa: E402
from app.services.quant_heatmaps import build_heatmaps  # noqa: E402
from app.services.quant_regime import build_regime  # noqa: E402
from app.services.quant_portfolio import build_portfolio, pick_basket  # noqa: E402
from app.services.quant_forecast import build_forecast  # noqa: E402
from app.services.quant_models import var_cvar  # noqa: E402
from app.services.concepts import REPOS, coverage_summary  # noqa: E402

client = TestClient(app)


def _no_nan(obj):
    """json.dumps with allow_nan=False raises on NaN/Inf anywhere in the tree."""
    json.dumps(obj, allow_nan=False)


@pytest.fixture(scope="module")
def aapl():
    return synthetic_history("AAPL", "max")


def test_clean_strips_nan_inf():
    out = clean({"a": float("nan"), "b": [float("inf"), 1.5], "c": {"d": -float("inf")}})
    assert out == {"a": None, "b": [None, 1.5], "c": {"d": None}}


def test_signals_valid(aapl):
    out = build_signals(aapl, "AAPL")
    assert out["success"]
    _no_nan(out)
    assert len(out["rules"]) == len(STRATEGIES)
    for r in out["rules"]:
        assert r["signal"] in ("BUY", "SELL", "NEUTRAL")
        assert r["insight"]["shows"] and r["insight"]["means"] and r["insight"]["action"]
        bt = r["backtest"]
        assert bt["signals"] >= 1
        if bt["hit_rate"] is not None:
            assert 0 <= bt["hit_rate"] <= 100
        assert bt["max_dd"] is None or bt["max_dd"] <= 0
    c = out["consensus"]
    assert -100 <= c["weighted_score"] <= 100
    assert c["buy"] + c["sell"] + c["neutral"] == c["total"]
    assert out["timeframe_heatmap"]["timeframes"] == ["Daily", "Weekly", "Monthly"]
    assert all(len(r["values"]) == 3 for r in out["horizon_heatmap"]["rows"])


def test_signals_short_history_rejected():
    out = build_signals(synthetic_history("AAPL", "max").tail(100), "AAPL")
    assert not out["success"]


def test_heatmaps_valid(aapl):
    bench = {k: synthetic_history(k, "5y")["Close"] for k in list(BENCH_NAMES)[:4]}
    out = build_heatmaps(aapl, "AAPL", bench)
    assert out["success"]
    _no_nan(out)
    m = out["monthly"]
    assert len(m["values"]) == len(m["years"]) and all(len(row) == 12 for row in m["values"])
    assert len(out["dow_month"]["values"]) == 5
    for row in out["dist_year"]["values"]:
        assert abs(sum(v for v in row if v is not None) - 100) < 1.0
    assert out["correlation"] and out["correlation"]["rows"]


def test_regime_valid(aapl):
    out = build_regime(aapl, "AAPL", synthetic_history("^GSPC", "max")["Close"], "^GSPC")
    assert out["success"]
    _no_nan(out)
    for k in ("rolling", "garch", "hurst", "regime", "mc_cone", "var", "tests", "beta", "drawdowns", "vol_cone"):
        assert out[k] is not None, k
        assert out[k]["insight"]["action"], k
    g = out["garch"]
    assert 0 < g["persistence"] < 1
    v = out["var"]["rows"][0]
    assert v["hist_var"] > 0 and v["param_var"] > 0 and v["hist_cvar"] >= v["hist_var"]
    hz = out["mc_cone"]["horizons"]
    assert [h["days"] for h in hz] == [21, 42, 63, 252]
    assert all(h["p5"] <= h["p50"] <= h["p95"] for h in hz)
    assert len(out["drawdowns"]["rows"]) <= 5


def test_parametric_var_positive():
    import numpy as np
    r = var_cvar(np.random.default_rng(1).normal(0, 0.01, 2000))
    assert r["var_param_pct"] > 0 and abs(r["var_param_pct"] - r["var_hist_pct"]) < 0.003


def test_portfolio_valid():
    basket = pick_basket("AAPL")
    assert basket[0] == "AAPL" and len(basket) >= 3
    out = build_portfolio("AAPL", {s: synthetic_history(s, "5y")["Close"] for s in basket})
    assert out["success"]
    _no_nan(out)
    for p in out["portfolios"]:
        assert abs(sum(p["weights"]) - 100) < 0.6
        assert min(p["weights"]) >= 0
    names = {p["name"] for p in out["portfolios"]}
    assert {"Minimum variance", "Maximum Sharpe", "Risk parity (ERC)", "Hierarchical Risk Parity"} <= names
    mv = next(p for p in out["portfolios"] if p["name"] == "Minimum variance")
    assert all(mv["vol_pct"] <= p["vol_pct"] + 0.05 for p in out["portfolios"])
    assert out["frontier"]


def test_forecast_valid(aapl):
    out = build_forecast(aapl, "AAPL")
    assert out["success"]
    _no_nan(out)
    models = {t["model"] for t in out["table"]}
    assert {"Naive", "Drift", "SES"} <= models
    assert all(t["mape"] >= 0 for t in out["table"])


def test_concepts_catalog():
    s = coverage_summary()
    assert s["concepts"] >= 120
    for r in REPOS:
        for c in r["concepts"]:
            assert c["status"] in ("implemented", "partial", "reference")
            assert c["where"] and c["meaning"]


@pytest.mark.parametrize("path", [
    "/api/v1/quant/signals/AAPL", "/api/v1/quant/heatmaps/AAPL", "/api/v1/quant/regime/AAPL",
    "/api/v1/quant/portfolio/AAPL", "/api/v1/quant/forecast/AAPL", "/api/v1/concepts",
    "/api/v1/analytics/charts/AAPL", "/api/v1/quant/stats/AAPL", "/api/v1/quant/risk/AAPL",
])
def test_endpoints_200(path):
    res = client.get(path)
    assert res.status_code == 200, res.text[:300]
    body = res.json()
    assert body.get("success", True)
