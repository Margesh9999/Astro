"""Tests for the v1.3 strategy area: TradingAgents pipeline + Final Strategy."""
import json
import math
import os

os.environ.setdefault("ASTRO_DEMO_DATA", "1")  # deterministic offline prices

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import agents_news  # noqa: E402
from app.services.agents import TradingAgentsEngine, rating_for  # noqa: E402

client = TestClient(app)


def _no_nan(o):
    if isinstance(o, dict):
        return all(_no_nan(v) for v in o.values())
    if isinstance(o, list):
        return all(_no_nan(v) for v in o)
    if isinstance(o, float):
        return math.isfinite(o)
    return True


def test_agents_endpoint_has_all_roles():
    r = client.get("/api/v1/agents/^GSPC", params={"rounds": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    names = {a["agent"] for a in d["analysts"]}
    assert {"Market (Technical) Analyst", "Fundamentals Analyst", "Sentiment (Social) Analyst",
            "News Analyst", "Astro Analyst"} <= names
    assert len(d["debate"]["rounds"]) == 3
    for rnd in d["debate"]["rounds"]:
        assert rnd["bull"]["text"] and rnd["bear"]["text"]
    assert d["research_manager"]["recommendation"] in ("BUY", "HOLD", "SELL")
    t = d["trader"]
    for k in ("action", "entry_low", "entry_high", "stop", "target_1", "target_2", "size_units"):
        assert k in t
    assert [v["stance"] for v in d["risk_team"]["views"]] == ["aggressive", "neutral", "conservative"]
    pm = d["portfolio_manager"]
    assert pm["rating"] in ("BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL")
    assert 0 < pm["confidence"] <= 100
    assert d["plain_english"]
    # backward compatible fields
    assert d["agents"] and d["manager"]["verdict"] == pm["rating"]
    assert "TradingAgents" in d["inspired_by"]
    assert _no_nan(d)


def test_news_degrades_honestly_in_demo_mode():
    n = agents_news.fetch_news("AAPL")
    assert n["available"] is False and "No news feed" in n["reason"]
    d = client.get("/api/v1/strategy/agents/^GSPC").json()
    news = next(a for a in d["analysts"] if a["key"] == "news")
    assert news["abstain"] is True and news["score"] == 0


def test_rating_ladder_and_empty_context():
    assert [rating_for(s) for s in (50, 20, 0, -20, -50)] == ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
    res = TradingAgentsEngine().analyse("X", "X", {"spot": 100.0}, rounds=1)
    assert res["decision"]["rating"] in ("BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL")
    json.dumps(res, allow_nan=False)


def test_final_strategy_endpoint():
    r = client.get("/api/v1/strategy/final/^GSPC", params={"capital": 60000, "target_weekly": 500})
    assert r.status_code == 200, r.text
    d = r.json()
    json.dumps(d, allow_nan=False)  # JSON clean
    assert _no_nan(d)
    assert [p["days"] for p in d["plans"]] == [30, 60, 90, 365]
    for p in d["plans"]:
        assert p["stance"] and p["approach"] and p["stop"] > 0 and p["entry_low"] <= p["entry_high"]
    keys = {row["key"] for row in d["scoreboard"]}
    assert {"technical", "quant", "ml", "suri", "sky", "agents", "natal", "dasha", "transits"} <= keys
    ml = next(x for x in d["scoreboard"] if x["key"] == "ml")
    if not ml["available"]:
        assert "train the model zoo" in ml["reason"].lower()
    nvt = d["natal_vs_today"]
    assert len(nvt["rows"]) == 9 and len(nvt["natal_chart"]) >= 9 and len(nvt["today_chart"]) == 9
    inc = d["income"]
    assert inc["target_weekly"] == 500
    rc = inc["required_capital"]
    assert rc["low"] > rc["base"] > rc["high"] > 0  # poor returns need MORE capital
    assert "not guaranteed" in d["risk_warning"].lower()
    assert d["bottom_line"] and d["weekly_routine"]


def test_final_strategy_custom_birth():
    r = client.get("/api/v1/strategy/final/^NSEI",
                   params={"name": "Test", "date": "1985-07-14", "time": "10:30", "place": "Mumbai"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["birth"].get("name") == "Test"
    assert len(d["plans"]) == 4
