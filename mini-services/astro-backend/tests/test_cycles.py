"""Cycles area: sky table, cycle stats, event study and endpoints (demo data)."""
import json
import math
import os

os.environ.setdefault("ASTRO_DEMO_DATA", "1")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.cycles_sky import SKY  # noqa: E402
from app.services.cycles_stats import cycle_stats  # noqa: E402
from app.services.events_study import events_with_study  # noqa: E402
from app.services.market_data import synthetic_history  # noqa: E402

client = TestClient(app)


def _all_finite(o):
    if isinstance(o, dict):
        return all(_all_finite(v) for v in o.values())
    if isinstance(o, list):
        return all(_all_finite(v) for v in o)
    if isinstance(o, float):
        return math.isfinite(o)
    return True


@pytest.fixture(scope="module")
def df():
    return synthetic_history("^GSPC", "max")


def test_sky_table_states_and_events():
    SKY.ensure()
    t = SKY.today_idx()
    assert 0 <= SKY.nakshatra[t] < 27 and 1 <= SKY.tithi[t] <= 30 and 0 <= SKY.phase8[t] < 8
    ev = SKY.events()
    fams = {e["family"] for e in ev}
    assert {"lunation", "eclipse", "station", "ingress", "aspect", "combustion"} <= fams
    # ~12.37 new moons a year
    news = [e for e in ev if e["key"] == "lunation:new"]
    years = SKY.n / 365.25
    assert abs(len(news) / years - 12.37) < 0.2
    # 2-3 Mercury retrograde stations a year
    mr = [e for e in ev if e["key"] == "station:Mercury:retro"]
    assert 2.8 < len(mr) / years < 3.4


def test_cycle_stats_finite(df):
    st = cycle_stats(df, "^GSPC", "S&P 500")
    assert st["success"]
    assert len(st["nakshatra"]["rows"]) == 27 and len(st["moon_phase"]["rows"]) == 8
    assert len(st["sun_sign"]["rows"]) == 12 and set(st["retrograde"]) == {"Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
    assert _all_finite(st)
    assert all(r["verdict"] in ("significant", "weak", "noise", "too few") for r in st["nakshatra"]["rows"])
    json.dumps(st, allow_nan=False)
    assert st["conclusions"]["overall"]


def test_event_study_outputs_finite(df):
    pack = events_with_study(df, "^GSPC", "S&P 500", "US Large Cap", 45)
    assert pack["success"] and pack["count"] > 0
    for e in pack["events"]:
        assert e["meaning"] and e["action"] and e["classical"]
        st = e["study"]
        if st["n"] >= 8:
            for k in ("1", "5", "20"):
                h = st["h"][k]
                assert np.isfinite([h["mean_pct"], h["base_pct"], h["hit_pct"], h["t"]]).all()
            assert st["vol_ratio"] > 0
    assert _all_finite(pack)
    json.dumps(pack, allow_nan=False)


def test_sector_touch_for_tech_stock(df):
    pack = events_with_study(df, "MSFT-TEST", "Microsoft", "Technology", 90)
    merc = [e for e in pack["events"] if "Mercury" in e["planets"]]
    assert merc and all(e["touches_stock"] for e in merc)


@pytest.mark.parametrize("url", [
    "/api/v1/cycles/clock",
    "/api/v1/cycles/stats/%5EGSPC",
    "/api/v1/cycles/insight/%5EGSPC",
    "/api/v1/events/study?symbol=%5EGSPC&days=45",
    "/api/v1/suri/cycles/%5EGSPC",
])
def test_endpoints_200_no_nan(url):
    r = client.get(url)
    assert r.status_code == 200, r.text[:300]
    assert "NaN" not in r.text and "Infinity" not in r.text
    assert _all_finite(r.json())


def test_insight_reading_is_actionable():
    d = client.get("/api/v1/cycles/insight/%5EGSPC").json()
    sents = d["reading"]["sentences"]
    assert 3 <= len(sents) <= 5
    assert any(s.startswith("What to do") for s in sents)
    assert {"mood", "reversal", "volatility", "range", "composite"} <= set(d["explain"])
    assert len(d["clock"]["items"]) == 8 and len(d["week"]["days"]) == 7 and len(d["lunar"]["days"]) == 30
