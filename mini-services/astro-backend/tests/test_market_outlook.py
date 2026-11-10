"""v1.6 market outlook: sector forecast, back-test and income plan (offline demo data)."""
from datetime import date

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services import market_outlook as M

client = TestClient(app)


def test_transit_table_dignity_and_penalties():
    t = M.table()
    i = M._idx(date(2026, 11, 5))
    assert 0.0 <= t["Jupiter"][i] <= 1.0
    # sidereal Jupiter is exalted in Cancer in Nov 2025 and retrograde in Gemini in Mar 2026
    j = M._idx(date(2025, 11, 1))
    assert int(t["Jupiter:sign"][j]) == 3 and t["Jupiter"][j] > M.NEUTRAL
    k = M._idx(date(2026, 3, 1))
    assert bool(t["Jupiter:retro"][k]) and t["Jupiter"][k] < t["Jupiter"][j]


def test_backtest_detects_planted_edge():
    idx = pd.bdate_range("2005-01-03", periods=4000)
    days = np.array([M._idx(d) for d in idx.date])
    zs = np.zeros(days.max() + 10)
    rng = np.random.default_rng(1)
    zs[days] = rng.choice([-1.0, 1.0], len(days))
    # price moves in the direction of z over each 5-session window
    rets = np.zeros(len(idx))
    for k in range(0, len(idx) - 5, 5):
        rets[k + 1:k + 6] = 0.002 * zs[days[k]]
    close = pd.Series(100 * np.exp(np.cumsum(rets)), index=idx)
    bt = M.backtest(close, zs, 5)
    assert bt["verdict"] == "significant edge" and bt["hit_pct"] > 95


def test_outlook_endpoint_shape():
    r = client.get("/api/v1/outlook", params={"date": "2026-11-05"})
    assert r.status_code == 200
    j = r.json()
    assert set(j["horizons"]) == {"week", "month", "year"}
    rows = j["horizons"]["month"]["sectors"]
    assert len(rows) == len(M.SECTORS)
    assert all(r["direction"] in ("up", "down", "range") for r in rows)
    assert all(r["options"]["income"] and r["options"]["trust"] for r in rows)
    assert [r["z"] for r in rows] == sorted((r["z"] for r in rows), reverse=True)
    plan = j["income_plan"]
    assert sum(b["allocation_pct"] for b in plan["buckets"]) in (99, 100, 101)
    assert "not financial advice" in j["disclaimer"]


def test_outlook_uses_jataka_fits():
    r = client.get("/api/v1/outlook", params={"date": "2026-11-05", "name": "Margesh", "birth_date": "1994-04-23",
                                              "time": "06:45", "place": "Vallabh Vidyanagar"})
    j = r.json()
    assert j["jataka"]["used"] is True
    plan = j["income_plan"]
    assert plan["split_source"] == "your chart's strategy fits"
    week = next(b for b in plan["buckets"] if b["horizon"] == "week")
    assert week["allocation_pct"] <= 30 and week["chart_fit"] is not None


def test_same_sector_mapping():
    assert M._same_sector("IT & telecom", "IT / CMT (tech, telecom, media)")
    assert not M._same_sector("IT & telecom", "Metals, mining, energy & utilities (MLEU)")
