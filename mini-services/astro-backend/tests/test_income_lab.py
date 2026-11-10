"""v1.7 income strategy lab and today's brief (offline demo data)."""
from fastapi.testclient import TestClient

from app.main import app
from app.services import income_lab as L

client = TestClient(app)


def test_put_spread_pays_credit_and_caps_loss():
    win = L.spread_trade(100.0, 105.0, 5 / 252, 0.2, "put_spread")
    assert win["credit"] > 0 and win["pnl"] > 0
    crash = L.spread_trade(100.0, 70.0, 5 / 252, 0.2, "put_spread")
    assert crash["pnl"] < 0
    # defined risk: the loss never exceeds the margin by more than trading costs
    assert -crash["pnl"] <= crash["margin"] * 1.05


def test_iron_condor_collects_more_than_one_side():
    pc = L.spread_trade(100.0, 100.0, 5 / 252, 0.2, "put_spread")
    ic = L.spread_trade(100.0, 100.0, 5 / 252, 0.2, "iron_condor")
    assert ic["credit"] > pc["credit"]


def test_income_lab_endpoint_shape_and_verdicts():
    r = client.get("/api/v1/income-lab", params={"strategy": "put_spread", "risk": 0.05})
    assert r.status_code == 200
    j = r.json()
    assert j["success"] and j["results"][0]["key"] == "none"
    assert {x["key"] for x in j["results"]} == set(L.FILTERS)
    for x in j["results"][1:]:
        assert x["verdict"] in ("helped beyond chance", "hurt beyond chance", "no better than skipping random weeks")
    assert j["this_week"]["advice"] and "Not financial advice" in j["disclaimer"]
    assert client.get("/api/v1/income-lab", params={"strategy": "naked_put"}).status_code == 400


def test_brief_combines_three_tiles():
    j = client.get("/api/v1/brief").json()
    assert j["success"] and "disclaimer" in j
    assert j["day"] is None or j["day"]["tone"] in ("favourable", "mixed", "caution")
    assert j["week"] is None or j["week"]["lean"] in ("up", "down", "range")
    assert j["trade"] is None or j["trade"]["win_rate_pct"] is not None
