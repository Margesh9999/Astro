"""v1.5 Astrologer Signals: track public calls by financial astrologers and score them.

How it works (no scraping of video content, no invented calls):

1. **Sources** are YouTube channels (Prashant Kapoor / @AstroKapoorcom is the default; users
   can add any other handle). The channel's public RSS feed lists its ~15 latest videos.
2. Each video **title + description** is tagged with a lexicon: which instrument it talks about
   (Nifty, Bank Nifty, Sensex, gold, S&P 500 …) and a direction (bullish / bearish / volatile /
   neutral). This is a heuristic reading of the *headline*, not of what was said in the video,
   and is labelled as such everywhere.
3. **Track record**: for each tagged video older than the horizon, the instrument's real return
   over the next N trading days is compared with the tagged direction. Hit rates are shown next
   to the instrument's base rate (how often it rises anyway), with the sample size.
4. **Consensus** for the selected symbol blends the recent tagged calls (newer = heavier).
5. Users can also **log their own calls** (e.g. "Kapoor said Nifty bearish 10-20 Nov"); the
   browser keeps them and ``score_calls`` grades them against real prices.

Everything is illustrative. A handful of headlines is a tiny sample; none of this is advice.
"""
from __future__ import annotations

import html
import logging
import math
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_SOURCES: List[Dict] = [
    {
        "id": "astrokapoor",
        "name": "Prashant Kapoor (AstroKapoor)",
        "handle": "@AstroKapoorcom",
        "url": "https://www.youtube.com/@AstroKapoorcom",
        "home_market": "^NSEI",
        "focus": "Indian indices (Nifty, Bank Nifty, Sensex), gold, global markets, via planetary transits",
    },
]

# instrument keyword -> (symbol, label). Longest patterns first so "bank nifty" beats "nifty".
INSTRUMENTS: List[Tuple[str, str, str]] = [
    (r"bank\s*nifty|banknifty|nifty\s*bank", "^NSEBANK", "Bank Nifty"),
    (r"nifty|\bnse\b", "^NSEI", "Nifty 50"),
    (r"sensex|\bbse\b", "^BSESN", "Sensex"),
    (r"\bgold\b", "GC=F", "Gold"),
    (r"\bsilver\b", "SI=F", "Silver"),
    (r"crude|\boil\b", "CL=F", "Crude oil"),
    (r"bitcoin|\bbtc\b|crypto", "BTC-USD", "Bitcoin"),
    (r"nasdaq", "^IXIC", "NASDAQ"),
    (r"dow\s*jones|\bdow\b", "^DJI", "Dow Jones"),
    (r"s\s*&\s*p|sp\s*500|s&p500|wall\s*street|us\s*market|american\s*market", "^GSPC", "S&P 500"),
    (r"ftse|uk\s*market", "^FTSE", "FTSE 100"),
    (r"dollar|usd\s*inr|rupee", "INR=X", "USD/INR"),
]
GENERIC_MARKET = re.compile(r"stock\s*market|share\s*market|market|sharemarket|indices|index", re.I)

BULL = {"bull", "bullish", "rally", "rallies", "rise", "rising", "up", "upside", "boom", "buy", "buying",
        "positive", "high", "highs", "record", "surge", "breakout", "golden", "gain", "gains", "uptrend",
        "recovery", "recover", "bounce", "growth", "opportunity", "tejee", "teji", "tezi", "तेजी"}
BEAR = {"bear", "bearish", "crash", "crashes", "fall", "falling", "down", "downside", "sell", "selling",
        "negative", "low", "lows", "correction", "collapse", "panic", "fear", "plunge", "slump", "recession",
        "war", "crisis", "danger", "warning", "downtrend", "bloodbath", "mandi", "mandee", "मंदी", "गिरावट"}
VOL = {"volatile", "volatility", "eclipse", "grahan", "retrograde", "vakri", "turmoil", "shock", "big move",
       "uncertain", "uncertainty", "swing", "swings", "turbulence", "storm"}
_WORD = re.compile(r"[a-zऀ-ॿ&]+")

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AstroTrader/1.5; +https://astrotrader-ten.vercel.app)",
                 "Accept-Language": "en-US,en;q=0.8"}
_CACHE: Dict[str, Tuple[float, object]] = {}
_TTL = 1800


def _cached(key: str, ttl: float, fn: Callable[[], object]) -> object:
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _CACHE[key] = (time.time(), val)
    return val


# ----------------------------------------------------------------------------- tagging

def detect_instruments(text: str) -> List[Dict]:
    t = (text or "").lower()
    out = []
    for pat, sym, label in INSTRUMENTS:
        if re.search(pat, t):
            out.append({"symbol": sym, "label": label})
            t = re.sub(pat, " ", t)  # consume, so "bank nifty" is not also counted as Nifty
    return out


def classify(text: str) -> Dict:
    """Heuristic direction of a headline: score in [-1, 1] plus a volatility flag."""
    t = (text or "").lower()
    words = _WORD.findall(t)
    b = sum(1 for w in words if w in BULL)
    s = sum(1 for w in words if w in BEAR)
    v = sum(1 for w in words if w in VOL) + sum(1 for p in ("big move",) if p in t)
    score = 0.0 if b + s == 0 else (b - s) / (b + s)
    if score >= 0.34:
        direction = "bullish"
    elif score <= -0.34:
        direction = "bearish"
    elif v:
        direction = "volatile"
    else:
        direction = "neutral"
    return {"direction": direction, "score": round(score, 2), "bull_hits": b, "bear_hits": s, "vol_hits": v}


def tag_video(v: Dict, home_market: str = "^NSEI") -> Dict:
    text = f"{v.get('title', '')} {v.get('description', '')[:600]}"
    inst = detect_instruments(text)
    if not inst and GENERIC_MARKET.search(text):
        label = next((lab for _, sym, lab in INSTRUMENTS if sym == home_market), home_market)
        inst = [{"symbol": home_market, "label": label, "inferred": True}]
    cls = classify(f"{v.get('title', '')} {v.get('title', '')} {v.get('description', '')[:300]}")  # title weighted x2
    return {**v, "instruments": inst, **cls}


# ----------------------------------------------------------------------------- YouTube

def _get(url: str, timeout: float = 12.0) -> str:
    with httpx.Client(headers=_HTTP_HEADERS, timeout=timeout, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.text


def resolve_channel_id(handle_or_url: str) -> Optional[str]:
    h = handle_or_url.strip()
    m = re.search(r"(UC[0-9A-Za-z_-]{22})", h)
    if m:
        return m.group(1)
    if not h.startswith("http"):
        h = "https://www.youtube.com/" + (h if h.startswith("@") else "@" + h)

    def fetch() -> Optional[str]:
        page = _get(h)
        for pat in (r'"externalId":"(UC[0-9A-Za-z_-]{22})"', r'"channelId":"(UC[0-9A-Za-z_-]{22})"',
                    r'channel/(UC[0-9A-Za-z_-]{22})'):
            mm = re.search(pat, page)
            if mm:
                return mm.group(1)
        return None

    return _cached(f"cid:{h.lower()}", 7 * 86400, fetch)  # type: ignore[return-value]


_NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
       "media": "http://search.yahoo.com/mrss/"}


def parse_feed(xml_text: str) -> Dict:
    root = ET.fromstring(xml_text)
    title = (root.findtext("a:title", default="", namespaces=_NS) or "").strip()
    vids = []
    for e in root.findall("a:entry", _NS):
        vid = e.findtext("yt:videoId", default="", namespaces=_NS)
        grp = e.find("media:group", _NS)
        desc = grp.findtext("media:description", default="", namespaces=_NS) if grp is not None else ""
        views = None
        if grp is not None:
            st = grp.find("media:community/media:statistics", _NS)
            if st is not None and st.get("views"):
                views = int(st.get("views"))
        vids.append({
            "video_id": vid,
            "title": html.unescape(e.findtext("a:title", default="", namespaces=_NS) or ""),
            "published": e.findtext("a:published", default="", namespaces=_NS),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "description": (desc or "").strip(),
            "views": views,
        })
    return {"channel_title": title, "videos": vids}


def fetch_feed(channel_id: str) -> Dict:
    def fetch() -> Dict:
        return parse_feed(_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"))
    return _cached(f"feed:{channel_id}", _TTL, fetch)  # type: ignore[return-value]


def source_for(handle: str) -> Dict:
    h = handle.strip()
    for s in DEFAULT_SOURCES:
        if s["handle"].lower() == h.lower() or s["id"] == h.lower():
            return dict(s)
    clean = h if h.startswith("@") or h.startswith("http") else "@" + h
    return {"id": re.sub(r"[^a-z0-9]+", "", clean.lower()) or "custom", "name": clean, "handle": clean,
            "url": clean if clean.startswith("http") else f"https://www.youtube.com/{clean}",
            "home_market": "^NSEI", "focus": "added by you"}


# ----------------------------------------------------------------------------- scoring

def _forward_return(px: pd.Series, start: datetime, days: int) -> Optional[Tuple[float, str, str]]:
    """Close-to-close return from the first session on/after ``start`` over ``days`` sessions."""
    idx = px.index
    if getattr(idx, "tz", None) is not None:
        px = px.tz_localize(None)
        idx = px.index
    st = pd.Timestamp(start).tz_localize(None) if pd.Timestamp(start).tzinfo else pd.Timestamp(start)
    pos = idx.searchsorted(st.normalize())
    if pos >= len(idx) or pos + days >= len(idx):
        return None
    a, b = float(px.iloc[pos]), float(px.iloc[pos + days])
    if a <= 0:
        return None
    return b / a - 1.0, str(idx[pos].date()), str(idx[pos + days].date())


def _base_rate(px: pd.Series, days: int) -> Tuple[float, float]:
    r = (px.shift(-days) / px - 1.0).dropna()
    r = r.iloc[-1500:] if len(r) > 1500 else r
    if r.empty:
        return 0.5, 0.0
    return float((r > 0).mean()), float(r.abs().mean())


def grade(direction: str, ret: float, typical_abs: float) -> Optional[bool]:
    if direction == "bullish":
        return ret > 0
    if direction == "bearish":
        return ret < 0
    if direction == "volatile":
        return abs(ret) > typical_abs
    return None


def score_videos(videos: List[Dict], history: Callable[[str], Optional[pd.Series]], horizon: int = 5) -> Dict:
    """Grade each tagged video against the next ``horizon`` sessions of its first instrument."""
    graded, per_symbol = [], {}
    now = datetime.now(timezone.utc)
    for v in videos:
        if v["direction"] == "neutral" or not v.get("instruments"):
            continue
        sym = v["instruments"][0]["symbol"]
        try:
            pub = datetime.fromisoformat(v["published"].replace("Z", "+00:00"))
        except Exception:
            continue
        px = history(sym)
        if px is None or len(px) < 50:
            continue
        if sym not in per_symbol:
            per_symbol[sym] = _base_rate(px, horizon)
        res = _forward_return(px, pub + timedelta(hours=12), horizon)
        if res is None:
            v["status"] = "pending" if (now - pub).days < horizon * 2 + 4 else "no data"
            continue
        ret, d0, d1 = res
        hit = grade(v["direction"], ret, per_symbol[sym][1])
        v.update({"status": "graded", "ret_pct": round(ret * 100, 2), "from": d0, "to": d1, "hit": hit})
        graded.append(v)
    n = sum(1 for g in graded if g["hit"] is not None)
    hits = sum(1 for g in graded if g["hit"])
    # what a coin-flip in the tagged direction would score, given each instrument's base rate
    exp = 0.0
    for g in graded:
        up, _ = per_symbol[g["instruments"][0]["symbol"]]
        exp += up if g["direction"] == "bullish" else (1 - up) if g["direction"] == "bearish" else 0.5
    out = {"horizon_days": horizon, "graded": n, "hits": hits,
           "hit_rate": round(hits / n * 100, 1) if n else None,
           "expected_by_chance": round(exp / n * 100, 1) if n else None}
    if n:
        p = exp / n
        z = (hits - n * p) / math.sqrt(n * p * (1 - p)) if 0 < p < 1 else 0.0
        out["z"] = round(z, 2)
        out["verdict"] = ("too few calls to judge" if n < 8 else
                          "better than chance" if z > 1.96 else
                          "worse than chance" if z < -1.96 else "indistinguishable from chance")
    else:
        out["verdict"] = "no gradable calls yet"
    return out


def consensus(videos: List[Dict], symbol: str, days: int = 21) -> Dict:
    now = datetime.now(timezone.utc)
    tot, wsum, used = 0.0, 0.0, []
    for v in videos:
        if not any(i["symbol"] == symbol for i in v.get("instruments", [])):
            continue
        try:
            age = (now - datetime.fromisoformat(v["published"].replace("Z", "+00:00"))).total_seconds() / 86400
        except Exception:
            continue
        if age > days or v["direction"] == "neutral":
            continue
        w = math.exp(-age / 7.0)
        s = {"bullish": 1.0, "bearish": -1.0}.get(v["direction"], 0.0)
        tot += w * s
        wsum += w
        used.append({"title": v["title"], "url": v["url"], "published": v["published"],
                     "direction": v["direction"], "source": v.get("source_name"), "weight": round(w, 2)})
    net = tot / wsum if wsum else 0.0
    lean = "bullish" if net > 0.25 else "bearish" if net < -0.25 else ("mixed / volatile" if used else "no recent calls")
    return {"symbol": symbol, "window_days": days, "net": round(net, 2), "lean": lean, "calls": used}


def score_calls(calls: List[Dict], history: Callable[[str], Optional[pd.Series]]) -> List[Dict]:
    """Grade user-logged calls: {source, symbol, direction, start, end, note?}."""
    out = []
    for c in calls[:200]:
        row = dict(c)
        try:
            px = history(c["symbol"])
            if px is None or px.empty:
                row["status"] = "no price data"
                out.append(row)
                continue
            p = px.copy()
            if getattr(p.index, "tz", None) is not None:
                p = p.tz_localize(None)
            s = pd.Timestamp(c["start"])
            e = pd.Timestamp(c.get("end") or c["start"])
            win = p[(p.index >= s - pd.Timedelta(days=4)) & (p.index <= e)]
            before = p[p.index < s]
            if before.empty or win.empty or p.index[-1] < e:
                row["status"] = "open (window not finished)" if p.index[-1] < e else "no price data"
                out.append(row)
                continue
            a = float(before.iloc[-1])
            b = float(p[p.index <= e].iloc[-1])
            ret = b / a - 1.0
            _, typ = _base_rate(p, max(1, len(p[(p.index >= s) & (p.index <= e)])))
            hit = grade(c.get("direction", "neutral"), ret, typ)
            row.update({"status": "graded", "ret_pct": round(ret * 100, 2), "hit": hit,
                        "max_move_pct": round((win.max() / a - 1) * 100, 2) if c.get("direction") == "bullish"
                        else round((win.min() / a - 1) * 100, 2)})
        except Exception as ex:  # one bad row never breaks the batch
            row["status"] = f"error: {ex}"
        out.append(row)
    return out


# ----------------------------------------------------------------------------- discovery

DISCOVER_QUERIES = ["stock market astrology prediction", "nifty astrology prediction",
                    "financial astrology market forecast"]


def _yt_search(query: str, limit: int = 12) -> List[Dict]:
    """Recent YouTube uploads for ``query`` (sorted by upload date) from the public results page."""
    import json
    from urllib.parse import quote_plus

    page = _get(f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=CAI%253D")
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", page, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))
    out: List[Dict] = []

    def walk(o):
        if len(out) >= limit:
            return
        if isinstance(o, dict):
            vr = o.get("videoRenderer")
            if isinstance(vr, dict) and vr.get("videoId"):
                title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", []))
                owner = "".join(r.get("text", "") for r in vr.get("ownerText", {}).get("runs", []))
                handle = ""
                try:
                    handle = vr["ownerText"]["runs"][0]["navigationEndpoint"]["browseEndpoint"].get("canonicalBaseUrl", "")
                except Exception:
                    pass
                snippet = "".join(r.get("text", "") for d in vr.get("detailedMetadataSnippets", [])
                                  for r in d.get("snippetText", {}).get("runs", []))
                out.append({"video_id": vr["videoId"], "title": title, "channel": owner,
                            "channel_url": f"https://www.youtube.com{handle}" if handle else "",
                            "published_text": vr.get("publishedTimeText", {}).get("simpleText", ""),
                            "url": f"https://www.youtube.com/watch?v={vr['videoId']}",
                            "description": snippet, "platform": "YouTube"})
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def _reddit_search(query: str, limit: int = 10) -> List[Dict]:
    import json
    from urllib.parse import quote_plus

    q = quote_plus(query)
    try:
        txt = _get(f"https://www.reddit.com/search.json?q={q}&sort=new&t=month&limit={limit}")
    except Exception:
        # the JSON API often refuses cloud IPs; the Atom feed is served more leniently
        return _reddit_rss(f"https://www.reddit.com/search.rss?q={q}&sort=new&t=month&limit={limit}")
    out = []
    for ch in json.loads(txt).get("data", {}).get("children", []):
        d = ch.get("data", {})
        out.append({"video_id": d.get("id", ""), "title": d.get("title", ""), "channel": f"r/{d.get('subreddit', '')}",
                    "channel_url": f"https://www.reddit.com/r/{d.get('subreddit', '')}",
                    "published": datetime.fromtimestamp(d.get("created_utc", 0), timezone.utc).isoformat(),
                    "url": f"https://www.reddit.com{d.get('permalink', '')}",
                    "description": (d.get("selftext") or "")[:600], "platform": "Reddit"})
    return out


def _reddit_rss(url: str) -> List[Dict]:
    import html as _html
    import re as _re
    import xml.etree.ElementTree as ET

    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(_get(url))
    out = []
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns)
        href = link.get("href", "") if link is not None else ""
        cat = e.find("a:category", ns)
        sub = cat.get("term", "") if cat is not None else ""
        body = _re.sub(r"<[^>]+>", " ", _html.unescape(e.findtext("a:content", "", ns)))
        out.append({"video_id": e.findtext("a:id", "", ns), "title": e.findtext("a:title", "", ns),
                    "channel": f"r/{sub}", "channel_url": f"https://www.reddit.com/r/{sub}",
                    "published": e.findtext("a:updated", "", ns) or e.findtext("a:published", "", ns),
                    "url": href, "description": " ".join(body.split())[:600], "platform": "Reddit"})
    return out


def discover(home_market: str = "^NSEI") -> Dict:
    """Recent financial-astrology predictions from YouTube search and Reddit (best effort)."""
    def run() -> Dict:
        items, errors = [], []
        for q in DISCOVER_QUERIES:
            try:
                items += _yt_search(q)
            except Exception as e:
                errors.append(f"YouTube search '{q}': {type(e).__name__}")
        try:
            items += _reddit_search("astrology stock market")
        except Exception as e:
            errors.append(f"Reddit: {type(e).__name__}")
        seen, uniq = set(), []
        for it in items:
            if it["url"] in seen or not it["title"]:
                continue
            seen.add(it["url"])
            uniq.append(tag_video(it, home_market))
        return {"items": uniq[:40], "errors": errors}
    return _cached(f"discover:{home_market}", _TTL, run)  # type: ignore[return-value]


# ----------------------------------------------------------------------------- insights

PLANET_TERMS = {
    "Saturn": r"saturn|shani|sade\s*sati", "Jupiter": r"jupiter|guru\b|brihaspati", "Rahu": r"\brahu\b",
    "Ketu": r"\bketu\b", "Mars": r"\bmars\b|mangal", "Mercury": r"mercury|budh", "Venus": r"venus|shukra",
    "Sun": r"\bsun\b|surya|sankranti", "Moon": r"\bmoon\b|chandra|amavasya|purnima|full moon|new moon",
}
EVENT_TERMS = {
    "eclipse": r"eclipse|grahan", "retrograde": r"retrograde|vakri", "transit": r"transit|gochar|enters|ingress",
    "conjunction": r"conjunction|yuti|combin", "Diwali / muhurat": r"diwali|muhurat|muhurta",
    "budget / election": r"budget|election|poll", "war / geopolitics": r"\bwar\b|geopolit|conflict|tension",
    "Fed / rates": r"\bfed\b|rate cut|rate hike|interest rate|rbi",
}
MONTHS = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b"


def insights(videos: List[Dict]) -> Dict:
    """Aggregate what the predictions are about: lean, instruments, planets, events, timing."""
    n = len(videos)
    if n == 0:
        return {"count": 0, "summary": "No predictions to summarise yet."}
    dirs = {d: sum(1 for v in videos if v["direction"] == d) for d in ("bullish", "bearish", "volatile", "neutral")}
    inst: Dict[str, int] = {}
    for v in videos:
        for i in v.get("instruments", []):
            inst[i["label"]] = inst.get(i["label"], 0) + 1
    def count(terms: Dict[str, str]) -> List[Tuple[str, int]]:
        out = []
        for k, pat in terms.items():
            c = sum(1 for v in videos if re.search(pat, f"{v['title']} {v.get('description', '')}", re.I))
            if c:
                out.append((k, c))
        return sorted(out, key=lambda x: -x[1])
    planets, events = count(PLANET_TERMS), count(EVENT_TERMS)
    months: Dict[str, int] = {}
    for v in videos:
        for m in re.findall(MONTHS, f"{v['title']} {v.get('description', '')}".lower()):
            k = m[:3].title()
            months[k] = months.get(k, 0) + 1
    top_inst = sorted(inst.items(), key=lambda x: -x[1])
    lean = max(("bullish", "bearish", "volatile"), key=lambda d: dirs[d])
    calls = dirs["bullish"] + dirs["bearish"] + dirs["volatile"]
    parts = [f"Out of {n} recent predictions, {calls} make a clear call: {dirs['bullish']} bullish, "
             f"{dirs['bearish']} bearish and {dirs['volatile']} warning of big moves."]
    if calls:
        parts.append(f"The crowd leans {lean}.")
    if top_inst:
        parts.append("Most discussed: " + ", ".join(f"{k} ({c})" for k, c in top_inst[:4]) + ".")
    if planets:
        parts.append("Planets cited most: " + ", ".join(f"{k} ({c})" for k, c in planets[:4]) + ".")
    if events:
        parts.append("Recurring themes: " + ", ".join(f"{k} ({c})" for k, c in events[:4]) + ".")
    if months:
        parts.append("Time windows named: " + ", ".join(f"{k} ({c})" for k, c in
                                                          sorted(months.items(), key=lambda x: -x[1])[:4]) + ".")
    parts.append("Astrologers often disagree and headlines exaggerate, so read this as a mood gauge, "
                 "not a forecast.")
    return {"count": n, "directions": dirs, "lean": lean if calls else "none", "instruments": top_inst[:8],
            "planets": planets[:8], "themes": events[:8], "months": sorted(months.items(), key=lambda x: -x[1])[:6],
            "summary": " ".join(parts)}
