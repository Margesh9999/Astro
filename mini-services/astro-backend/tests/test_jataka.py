import json
import math
import os
from datetime import datetime

os.environ.setdefault("ASTRO_DEMO_DATA", "1")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.jataka import JatakaEngine  # noqa: E402
from app.services.jataka_geo import PLACES, local_to_utc, resolve_place, search_places  # noqa: E402

client = TestClient(app)


def _no_nan(o):
    if isinstance(o, float):
        assert not (math.isnan(o) or math.isinf(o))
    elif isinstance(o, dict):
        for v in o.values():
            _no_nan(v)
    elif isinstance(o, list):
        for v in o:
            _no_nan(v)


# ── time zones ──
def test_uk_summer_birth_uses_bst():
    utc, off, dst, tz = local_to_utc("1990-07-15", "10:00", "Europe/London")
    assert (utc, off, dst, tz) == (datetime(1990, 7, 15, 9, 0), 1.0, True, "Europe/London")


def test_uk_winter_birth_uses_gmt_and_us_dst():
    assert local_to_utc("1990-01-15", "10:00", "Europe/London")[0] == datetime(1990, 1, 15, 10, 0)
    # New York summer (EDT, UTC-4)
    assert local_to_utc("2000-07-04", "12:00", "America/New_York")[1] == -4.0


def test_manual_offset_overrides_zone():
    utc, off, dst, _ = local_to_utc("1990-07-15", "10:00", "Europe/London", tz_offset=0.0)
    assert utc == datetime(1990, 7, 15, 10, 0) and off == 0.0 and dst is False


def test_uk_summer_chart_shifts_one_hour():
    e = JatakaEngine()
    bst = e.compute_chart(date="1990-07-15", time="10:00", place="London")
    assert bst["birth"]["utc"] == "1990-07-15T09:00:00" and bst["birth"]["dst"] is True


# ── gazetteer ──
def test_gazetteer_size_and_lookup():
    assert len(PLACES) >= 250
    assert all(p["tz_name"] for p in PLACES)
    assert resolve_place("London")["tz_name"] == "Europe/London"
    assert resolve_place("Vallabh Vidyanagar, Gujarat, India")["lat"] == 22.5347
    assert search_places("toron")[0]["name"].startswith("Toronto")
    for cap in ("Gandhinagar", "Itanagar", "Kohima", "Port Blair", "Thiruvananthapuram"):
        assert resolve_place(cap), cap


# ── default native chart ──
def test_default_native_chart():
    ch = JatakaEngine().compute_chart()
    p = ch["positions"]
    assert ch["birth"]["name"] == "Margesh"
    assert p["Lagna"]["sign"] == "Aries"
    assert p["Moon"]["sign"] == "Leo"
    assert (p["Moon"]["nakshatra"], p["Moon"]["pada"]) == ("Uttara Phalguni", 1)
    assert ch["birth"]["utc"] == "1994-04-23T01:15:00"


def test_true_node_and_ayanamsa_options():
    e = JatakaEngine()
    mean = e.compute_chart(node="mean")["positions"]["Rahu"]["longitude"]
    true = e.compute_chart(node="true")["positions"]["Rahu"]["longitude"]
    assert 0.1 < abs(mean - true) < 2.5
    trop = e.compute_chart(ayanamsa="tropical")
    assert trop["ayanamsa"] == 0.0
    kp = e.compute_chart(ayanamsa="kp")["ayanamsa"]
    lah = e.compute_chart()["ayanamsa"]
    assert abs(kp - lah) < 0.2


def test_dasha_current_rahu_ketu():
    d = JatakaEngine().compute_chart()["dasha"]
    cur = d.trading_now(datetime(2026, 10, 27))
    assert cur["mahadasha"]["lord"] == "Rahu" and cur["antardasha"]["lord"] == "Ketu"
    assert cur["pratyantardasha"]["meaning"]


# ── endpoints ──
def test_report_default_name_and_pds():
    r = client.get("/api/v1/jataka/report")
    assert r.status_code == 200
    j = r.json()
    _no_nan(j)
    assert j["birth"]["name"] == "Margesh"
    ad = j["dasha_tree"]["mahadashas"][1]["antardashas"][0]
    assert len(ad["pratyantardashas"]) == 9
    assert j["plan"]["markets"] and j["plan"]["lifetime"]["rows"]


def test_stock_correlation_endpoint_clean():
    r = client.get("/api/v1/jataka/stock-correlation", params={"symbol": "^NSEI"})
    assert r.status_code == 200
    j = r.json()
    json.dumps(j, allow_nan=False)
    assert j["success"] and j["verdict"]["actions"]
    assert j["periods"]["ad_by_lord"] and j["transits"]["rows"]
    assert 0 <= j["synastry"]["score"] <= 100


def test_planetary_observer_location():
    a = client.get("/api/v1/planetary/2026-10-28", params={"vedic": True, "at": "00:15"}).json()
    b = client.get("/api/v1/planetary/2026-10-28",
                   params={"vedic": True, "at": "00:15", "lat": 51.5, "lon": -0.12}).json()
    assert a["observer"]["lat"] == 23.1793
    assert a["planetary_positions"]["Lagna"]["sign"] != b["planetary_positions"]["Lagna"]["sign"]


def test_non_lahiri_ayanamsa_does_not_leak():
    import swisseph as swe
    jd = swe.julday(2026, 10, 28, 0.0)
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    before = swe.get_ayanamsa_ut(jd)
    e = JatakaEngine()
    e.compute_chart(ayanamsa="kp")
    e.full_report(ayanamsa="raman")
    client.get("/api/v1/jataka/stock-correlation", params={"symbol": "^NSEI", "ayanamsa": "kp"})
    assert swe.get_ayanamsa_ut(jd) == before
