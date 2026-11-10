"""v1.5 Astrologer Signals (mounted under /api/v1 by app.main).

  GET  /astrologers/sources                      default tracked sources
  GET  /astrologers/feed?handles=@A,@B&symbol=&horizon=5
                                                 latest videos per source, tagged; track record;
                                                 consensus for ``symbol``
  GET  /astrologers/discover?symbol=           recent predictions found via YouTube search + Reddit
  POST /astrologers/score   {calls:[...]}        grade user-logged calls against real prices
"""
import logging
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.routes import market_service
from app.services import astrologers as A
from app.services.market_data import DEMO_DATA

logger = logging.getLogger(__name__)
router = APIRouter()

DISCLAIMER = ("Directions are a keyword reading of public video titles/descriptions, not of what was said "
              "in the video. Track records use small samples. Illustrative only; not financial advice.")


def _history(symbol: str) -> Optional[pd.Series]:
    try:
        df = market_service.fetch_historical_data(symbol, period="5y", interval="1d")
        if df is None or df.empty:
            return None
        return df["Close"].dropna()
    except Exception as e:
        logger.warning(f"astrologers: no history for {symbol}: {e}")
        return None


@router.get("/astrologers/sources")
def sources():
    return {"success": True, "sources": A.DEFAULT_SOURCES, "disclaimer": DISCLAIMER}


@router.get("/astrologers/feed")
def feed(handles: str = "", symbol: str = "^NSEI", horizon: int = 5):
    horizon = max(1, min(int(horizon), 30))
    hs = [h.strip() for h in handles.split(",") if h.strip()][:6] or [s["handle"] for s in A.DEFAULT_SOURCES]
    out_sources: List[Dict] = []
    all_videos: List[Dict] = []
    for h in hs:
        src = A.source_for(h)
        row = {**src, "ok": False}
        try:
            cid = A.resolve_channel_id(src["handle"])
            if not cid:
                raise ValueError("could not resolve the YouTube channel")
            fd = A.fetch_feed(cid)
            vids = [A.tag_video({**v, "source_id": src["id"], "source_name": src["name"]}, src["home_market"])
                    for v in fd["videos"]]
            row.update({"ok": True, "channel_id": cid, "channel_title": fd["channel_title"] or src["name"],
                        "videos": vids, "track_record": A.score_videos(vids, _history, horizon)})
            all_videos.extend(vids)
        except Exception as e:
            logger.warning(f"astrologer feed failed for {h}: {e}")
            row["error"] = f"feed unavailable ({type(e).__name__}): {e}"[:200]
        out_sources.append(row)
    return {"success": True, "symbol": symbol, "horizon_days": horizon, "sources": out_sources,
            "consensus": A.consensus(all_videos, symbol), "insights": A.insights(all_videos),
            "demo_prices": DEMO_DATA,
            "method": ("Each video's title and description are tagged with the instrument(s) it names and a "
                       "bullish / bearish / volatile lean from a keyword list. Calls older than the horizon "
                       f"are graded on the instrument's next {horizon} trading sessions and compared with "
                       "how often a coin-flip in that direction would have been right."),
            "disclaimer": DISCLAIMER}


@router.get("/astrologers/discover")
def discover(symbol: str = "^NSEI"):
    """Recent financial-astrology predictions found on YouTube search and Reddit, tagged and summarised."""
    d = A.discover("^NSEI")
    items = d["items"]
    return {"success": True, "items": items, "insights": A.insights(items),
            "consensus": A.consensus(items, symbol, days=30), "errors": d["errors"],
            "sources_searched": ["YouTube search: " + q for q in A.DISCOVER_QUERIES] + ["Reddit search"],
            "note": ("X / Instagram / Facebook need a signed-in API, so they are not searched. "
                     "YouTube search items show the platform's own 'x days ago' text."),
            "disclaimer": DISCLAIMER}


class Call(BaseModel):
    source: str = ""
    symbol: str
    direction: str
    start: str
    end: Optional[str] = None
    note: Optional[str] = None
    link: Optional[str] = None


class ScoreReq(BaseModel):
    calls: List[Call]


@router.post("/astrologers/score")
def score(req: ScoreReq):
    try:
        rows = A.score_calls([c.model_dump() for c in req.calls], _history)
        by_src: Dict[str, Dict] = {}
        for r in rows:
            if r.get("status") != "graded" or r.get("hit") is None:
                continue
            b = by_src.setdefault(r.get("source") or "unknown", {"graded": 0, "hits": 0})
            b["graded"] += 1
            b["hits"] += int(bool(r["hit"]))
        for b in by_src.values():
            b["hit_rate"] = round(b["hits"] / b["graded"] * 100, 1)
        return {"success": True, "calls": rows, "by_source": by_src, "disclaimer": DISCLAIMER}
    except Exception as e:
        logger.error(f"astrologer score error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
