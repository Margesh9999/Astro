"""v1.4 panchang: limbs are internally consistent and the API/ICS endpoints respond."""
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services.panchang import karana_name, market_calendar, panchang, tithi_label

client = TestClient(app)


def test_tithi_and_karana_labels():
    assert tithi_label(15) == ("Shukla", "Purnima")
    assert tithi_label(30) == ("Krishna", "Amavasya")
    assert tithi_label(16) == ("Krishna", "Pratipada")
    assert karana_name(1) == "Kimstughna" and karana_name(60) == "Naga"
    assert karana_name(2) == "Bava" and karana_name(8) == "Vishti"


def test_known_diwali_amavasya_2026():
    # Diwali (Lakshmi Puja) 2026 falls on the Kartika Amavasya, 8 Nov 2026 (India)
    days = [panchang(date(2026, 11, d)) for d in (7, 8, 9)]
    assert any(p["tithi"]["name"] in ("Amavasya", "Chaturdashi") for p in days)
    assert any("Amavasya" in p["tithi"]["name"] or "Amavasya" in p["flags"] for p in days[1:])


def test_panchang_shape_and_order():
    p = panchang(date(2026, 11, 4))
    assert p["sunrise"] < p["sunset"] < p["next_sunrise"]
    for limb in ("tithi", "nakshatra", "yoga", "karana"):
        assert p[limb]["ends"] > p["sunrise"]
    assert 1 <= p["tithi"]["index"] <= 30 and 0 <= p["nakshatra"]["index"] < 27
    assert p["vara"]["weekday"] == "Wednesday"
    assert p["tone"] in ("favourable", "mixed", "caution")
    assert "not a trading signal" in p["plain_english"]


def test_calendar_and_events():
    c = market_calendar(date(2026, 11, 4), 30)
    assert len(c["rows"]) == 30
    titles = [e["title"] for e in c["events"]]
    assert "Sun enters Scorpio" in titles  # Vrishchika Sankranti, mid-November


def test_endpoints():
    r = client.get("/api/v1/panchang", params={"date": "2026-11-04"})
    assert r.status_code == 200 and r.json()["success"]
    r = client.get("/api/v1/panchang/calendar", params={"start": "2026-11-04", "days": 7})
    assert r.status_code == 200 and len(r.json()["rows"]) == 7
    r = client.get("/api/v1/panchang/calendar.ics", params={"start": "2026-11-04", "days": 7})
    assert r.status_code == 200 and r.text.startswith("BEGIN:VCALENDAR")
    assert client.get("/api/v1/panchang", params={"date": "bad"}).status_code == 400
