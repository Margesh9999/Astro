"""
News + sentiment feed for the TradingAgents analyst team.

Live mode: yfinance ``Ticker(symbol).news`` headlines scored with a small
finance lexicon (no external NLP dependency). Demo mode (ASTRO_DEMO_DATA=1)
or any failure returns an honest "no news feed available" payload — the
agents then give the News/Sentiment analysts zero weight instead of making
something up.
"""
from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from typing import Dict, List

logger = logging.getLogger(__name__)

DEMO = os.environ.get("ASTRO_DEMO_DATA", "").lower() in ("1", "true", "yes")
_CACHE: Dict[str, tuple] = {}
_TTL = 900  # 15 min
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="agents-news")

POS = {
    "beat", "beats", "surge", "surges", "soar", "soars", "rally", "rallies", "gain", "gains",
    "record", "upgrade", "upgrades", "upgraded", "strong", "growth", "profit", "profits",
    "bullish", "outperform", "raise", "raises", "raised", "boost", "boosts", "jump", "jumps",
    "rebound", "rebounds", "optimism", "optimistic", "buy", "expands", "wins", "approval",
    "high", "highs", "climb", "climbs", "positive", "tops", "exceeds", "recovery",
}
NEG = {
    "miss", "misses", "plunge", "plunges", "slump", "slumps", "fall", "falls", "drop", "drops",
    "downgrade", "downgrades", "downgraded", "weak", "loss", "losses", "bearish", "cut", "cuts",
    "lawsuit", "probe", "investigation", "recession", "fears", "fear", "warning", "warns",
    "decline", "declines", "sell-off", "selloff", "crash", "tumble", "tumbles", "slides",
    "concern", "concerns", "risk", "risks", "layoffs", "inflation", "tariff", "tariffs",
    "low", "lows", "negative", "default", "bankruptcy", "volatile", "uncertainty",
}
_WORD = re.compile(r"[a-z][a-z\-']+")


def score_headline(text: str) -> float:
    """Lexicon polarity in [-1, 1]."""
    words = _WORD.findall((text or "").lower())
    p = sum(1 for w in words if w in POS)
    n = sum(1 for w in words if w in NEG)
    if p + n == 0:
        return 0.0
    return round((p - n) / (p + n), 2)


def _extract(item: Dict) -> Dict:
    # yfinance >=0.2.5x nests the payload under "content"
    c = item.get("content") if isinstance(item.get("content"), dict) else item
    title = c.get("title") or item.get("title") or ""
    pub = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else None
    pub = pub or item.get("publisher") or ""
    when = c.get("pubDate") or c.get("displayTime") or item.get("providerPublishTime") or ""
    if isinstance(when, (int, float)):
        when = time.strftime("%Y-%m-%d", time.gmtime(when))
    link = ""
    for k in ("canonicalUrl", "clickThroughUrl"):
        if isinstance(c.get(k), dict) and c[k].get("url"):
            link = c[k]["url"]
            break
    link = link or item.get("link") or ""
    return {"title": str(title)[:220], "publisher": str(pub)[:60], "date": str(when)[:10], "url": str(link)}


def _fetch_raw(symbol: str) -> List[Dict]:
    import yfinance as yf  # local import: heavy and optional
    return list(yf.Ticker(symbol).news or [])


def fetch_news(symbol: str, limit: int = 8, timeout: float = 4.0) -> Dict:
    """Headlines + lexicon sentiment. Never raises."""
    if DEMO:
        return {"available": False, "headlines": [], "avg_sentiment": 0.0,
                "reason": "No news feed available (offline demo-data mode) — news analyst abstains."}
    hit = _CACHE.get(symbol)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    try:
        raw = _POOL.submit(_fetch_raw, symbol).result(timeout=timeout)
        heads = []
        for it in raw[:limit]:
            h = _extract(it)
            if not h["title"]:
                continue
            h["sentiment"] = score_headline(h["title"])
            heads.append(h)
        if not heads:
            out = {"available": False, "headlines": [], "avg_sentiment": 0.0,
                   "reason": "No news feed available for this symbol right now — news analyst abstains."}
        else:
            avg = sum(h["sentiment"] for h in heads) / len(heads)
            out = {"available": True, "headlines": heads, "avg_sentiment": round(avg, 2),
                   "positive": sum(1 for h in heads if h["sentiment"] > 0),
                   "negative": sum(1 for h in heads if h["sentiment"] < 0),
                   "reason": f"{len(heads)} recent Yahoo Finance headlines scored with a finance word list."}
    except FutTimeout:
        out = {"available": False, "headlines": [], "avg_sentiment": 0.0,
               "reason": "No news feed available (news request timed out) — news analyst abstains."}
    except Exception as exc:  # network blocked, schema change, etc.
        logger.info("news feed unavailable for %s: %s", symbol, exc)
        out = {"available": False, "headlines": [], "avg_sentiment": 0.0,
               "reason": "No news feed available (source unreachable) — news analyst abstains."}
    _CACHE[symbol] = (time.time(), out)
    return out


_FCACHE: Dict[str, tuple] = {}
_FKEYS = ("trailingPE", "forwardPE", "priceToBook", "profitMargins", "revenueGrowth",
          "earningsGrowth", "dividendYield", "debtToEquity", "returnOnEquity", "recommendationKey")


def _fetch_info(symbol: str) -> Dict:
    import yfinance as yf
    return dict(yf.Ticker(symbol).info or {})


def fetch_fundamentals(symbol: str, timeout: float = 4.0) -> Dict:
    """Company fundamentals from yfinance .info (live mode only). Never raises."""
    if DEMO or symbol.startswith("^"):
        why = ("offline demo-data mode" if DEMO else "indices have no company fundamentals")
        return {"available": False, "metrics": {}, "reason": f"No fundamentals feed ({why})."}
    hit = _FCACHE.get(symbol)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    try:
        info = _POOL.submit(_fetch_info, symbol).result(timeout=timeout)
        m = {}
        for k in _FKEYS:
            v = info.get(k)
            if isinstance(v, (int, float)) and v == v and abs(v) != float("inf"):
                m[k] = round(float(v), 4)
            elif isinstance(v, str):
                m[k] = v
        out = ({"available": True, "metrics": m, "reason": "Yahoo Finance company snapshot."} if m else
               {"available": False, "metrics": {}, "reason": "No fundamentals returned for this symbol."})
    except Exception as exc:
        logger.info("fundamentals unavailable for %s: %s", symbol, exc)
        out = {"available": False, "metrics": {}, "reason": "No fundamentals feed (source unreachable)."}
    _FCACHE[symbol] = (time.time(), out)
    return out
