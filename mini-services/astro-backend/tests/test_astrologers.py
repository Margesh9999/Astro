"""v1.5 astrologer signals: tagging, feed parsing, grading, consensus and the API (offline)."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services import astrologers as A

client = TestClient(app)
NOW = datetime.now(timezone.utc)


def _feed_xml(entries):
    items = "".join(
        f"""<entry><yt:videoId>{vid}</yt:videoId><title>{title}</title><published>{pub}</published>
        <media:group><media:description>{desc}</media:description>
        <media:community><media:statistics views="1234"/></media:community></media:group></entry>"""
        for vid, title, pub, desc in entries)
    return f"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/">
      <title>AstroKapoor</title>{items}</feed>"""


def test_instrument_detection_and_direction():
    ins = [i["symbol"] for i in A.detect_instruments("Bank Nifty and Gold outlook; NIFTY crash?")]
    assert ins[:3] == ["^NSEBANK", "^NSEI", "GC=F"]
    assert A.detect_instruments("Golden opportunity, turmoil ahead") == []
    assert A.classify("Nifty crash and panic ahead, sell")["direction"] == "bearish"
    assert A.classify("Huge rally, bullish breakout to record highs")["direction"] == "bullish"
    assert A.classify("Solar eclipse: what to expect")["direction"] == "volatile"
    assert A.classify("Weekly horoscope")["direction"] == "neutral"


def test_generic_market_maps_to_home_market():
    v = A.tag_video({"title": "Stock market crash coming?", "description": ""}, "^NSEI")
    assert v["instruments"][0]["symbol"] == "^NSEI" and v["instruments"][0].get("inferred")
    assert v["direction"] == "bearish"


def test_parse_feed():
    fd = A.parse_feed(_feed_xml([("abc", "Nifty rally &amp; gold", "2026-10-01T10:00:00+00:00", "d")]))
    assert fd["channel_title"] == "AstroKapoor"
    assert fd["videos"][0]["title"] == "Nifty rally & gold" and fd["videos"][0]["views"] == 1234


def _rising(n=600):
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.Series(np.linspace(100, 200, n), index=idx)


def test_score_videos_and_consensus():
    vids = [A.tag_video({"title": t, "description": "", "published": (NOW - timedelta(days=d)).isoformat(),
                         "url": "u", "source_name": "S"}) for t, d in
            [("Nifty bullish rally", 40), ("Nifty crash warning", 30), ("Nifty bullish breakout", 2)]]
    tr = A.score_videos(vids, lambda s: _rising(), horizon=5)
    assert tr["graded"] == 2 and tr["hits"] == 1  # bullish right, bearish wrong on a rising series
    assert vids[2]["status"] == "pending"
    c = A.consensus(vids, "^NSEI", days=21)
    assert c["lean"] == "bullish" and len(c["calls"]) == 1


def test_score_calls():
    px = _rising()
    d0 = px.index[-30].date().isoformat()
    d1 = px.index[-20].date().isoformat()
    rows = A.score_calls([{"source": "Kapoor", "symbol": "^NSEI", "direction": "bearish", "start": d0, "end": d1},
                          {"source": "Kapoor", "symbol": "^NSEI", "direction": "bullish", "start": d0,
                           "end": (pd.Timestamp.today() + pd.Timedelta(days=30)).date().isoformat()}],
                         lambda s: px)
    assert rows[0]["status"] == "graded" and rows[0]["hit"] is False and rows[0]["ret_pct"] > 0
    assert rows[1]["status"].startswith("open")


def test_feed_endpoint_offline(monkeypatch):
    xml = _feed_xml([("v1", "Nifty crash warning", (NOW - timedelta(days=40)).isoformat(), ""),
                     ("v2", "Bank Nifty bullish", (NOW - timedelta(days=3)).isoformat(), "")])

    def fake_get(url, timeout=12.0):
        return xml if "feeds/videos.xml" in url else '{"externalId":"UCabcdefghijklmnopqrstuv"}'
    monkeypatch.setattr(A, "_get", fake_get)
    A._CACHE.clear()
    r = client.get("/api/v1/astrologers/feed", params={"symbol": "^NSEBANK"})
    j = r.json()
    assert r.status_code == 200 and j["sources"][0]["ok"], j
    assert j["sources"][0]["channel_id"] == "UCabcdefghijklmnopqrstuv"
    assert j["consensus"]["lean"] == "bullish"
    r = client.post("/api/v1/astrologers/score", json={"calls": [
        {"source": "X", "symbol": "^NSEI", "direction": "bullish", "start": "2024-01-02", "end": "2024-01-10"}]})
    assert r.status_code == 200 and r.json()["calls"][0]["status"] in ("graded", "no price data")


def test_insights_and_discover(monkeypatch):
    vids = [A.tag_video({"title": t, "description": d, "published": NOW.isoformat(), "url": f"u{i}"})
            for i, (t, d) in enumerate([("Nifty crash in November due to Saturn retrograde", ""),
                                        ("Gold rally as Jupiter enters Cancer", "big gains in December"),
                                        ("Solar eclipse market prediction", "Rahu Ketu axis")])]
    ins = A.insights(vids)
    assert ins["count"] == 3 and ins["directions"]["bearish"] == 1 and ins["directions"]["bullish"] == 1
    assert dict(ins["planets"])["Saturn"] == 1 and dict(ins["themes"])["eclipse"] == 1
    assert dict(ins["months"])["Nov"] == 1 and "mood gauge" in ins["summary"]

    page = ('<script>var ytInitialData = {"contents":[{"videoRenderer":{"videoId":"abc",'
            '"title":{"runs":[{"text":"Nifty prediction: bullish breakout"}]},'
            '"ownerText":{"runs":[{"text":"Some Astro","navigationEndpoint":{"browseEndpoint":{"canonicalBaseUrl":"/@someastro"}}}]},'
            '"publishedTimeText":{"simpleText":"2 days ago"}}}]};</script>')
    reddit = '{"data":{"children":[{"data":{"id":"r1","title":"Astrology says market crash","subreddit":"x","permalink":"/r/x/1","created_utc":1790000000}}]}}'
    monkeypatch.setattr(A, "_get", lambda url, timeout=12.0: reddit if "reddit" in url else page)
    A._CACHE.clear()
    j = client.get("/api/v1/astrologers/discover").json()
    assert j["success"] and {i["platform"] for i in j["items"]} == {"YouTube", "Reddit"}
    yt = next(i for i in j["items"] if i["platform"] == "YouTube")
    assert yt["direction"] == "bullish" and yt["channel_url"].endswith("/@someastro")
