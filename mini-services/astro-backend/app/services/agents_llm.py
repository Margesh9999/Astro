"""
Optional Claude narration for the TradingAgents debate.

Only active when ANTHROPIC_API_KEY is set AND the ``anthropic`` package is
installed. Each call is short, time-boxed, and any error (missing SDK, network,
refusal, timeout) returns ``None`` so the caller keeps the rule-based text.
The numbers and the decision always come from the deterministic engine; Claude
only rewrites the explanation in plain English.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-5-5"
SYSTEM = (
    "You are one role in a TradingAgents-style research desk for an educational app. "
    "Rewrite the analyst note you are given in 2-4 short sentences of plain English for a retail "
    "investor. Keep every number exactly as given, do not invent data, do not change the stance, "
    "and never promise returns. No headings, no bullet points."
)


def available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def _client():
    import anthropic
    return anthropic.Anthropic(timeout=12.0, max_retries=0)


def _one(client, role: str, note: str) -> Optional[str]:
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": f"Role: {role}\nNote: {note}"}],
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return None
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text").strip()
        return text or None
    except Exception as exc:  # any SDK / network / validation error -> rules
        logger.info("LLM narration failed for %s: %s", role, exc)
        return None


def narrate(items: List[Dict], budget_s: float = 25.0) -> Dict[str, str]:
    """items: [{"key", "role", "text"}] -> {key: rewritten_text} (missing keys = keep rules)."""
    if not items or not available():
        return {}
    try:
        client = _client()
    except Exception as exc:
        logger.info("anthropic client init failed: %s", exc)
        return {}
    out: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(items))) as pool:
        futs = {pool.submit(_one, client, it["role"], it["text"]): it["key"] for it in items}
        try:
            for f in as_completed(futs, timeout=budget_s):
                txt = f.result()
                if txt:
                    out[futs[f]] = txt
        except Exception as exc:  # overall budget exceeded
            logger.info("LLM narration budget exceeded: %s", exc)
    return out
