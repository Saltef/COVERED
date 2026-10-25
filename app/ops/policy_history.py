"""Policy history: the drift checker's shared, queryable memory.

This is what makes SurrealDB Agent Memory part of the loop rather than a demo. When the drift
checker confirms a figure (its generator and verifier agents agree, high confidence), that reading
is written here as a fact with real provenance: the value, the official source URL, the date it was
seen, and the verbatim quote it was grounded on. A changed value supersedes the prior fact for the
same figure, so the memory is a time-aware record of what each figure was and when.

Only public policy figures are ever written here; no user, health, or income data. See
app.ops.agent_memory for the PHIPA boundary.

Everything degrades gracefully: with no SPECTRON_* configured, available() is False and the
recorders no-op, so the drift checker still runs and reports.
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Optional

from app.ops import agent_memory as mem

log = logging.getLogger(__name__)


def available() -> bool:
    return mem.available()


def record_check(result, source_url: str = "", seen_date: str = "") -> Optional[dict]:
    """Write one confident drift-check reading to memory, with provenance. No-op unless memory is
    configured and the result is verifier-confident (a definitive match or mismatch). Returns the
    service response, or None when skipped."""
    if not available():
        return None
    if result.status not in ("match", "mismatch") or result.confidence != "high":
        return None  # only assert facts the verifier stood behind
    if result.extracted_value is None:
        return None
    seen = seen_date or _dt.date.today().isoformat()
    display = _format_value(result.extracted_value)
    try:
        return mem.publish_policy_fact(result.label, display, source_url or "official source",
                                       seen, result.quote)
    except Exception as exc:  # noqa: BLE001  never let a memory write break the check
        log.info("policy_history write failed for %s: %s", result.id, type(exc).__name__)
        return None


def record_registry_value(rule) -> Optional[dict]:
    """Seed/refresh the current engine value for one registry rule as a fact with its source."""
    if not available():
        return None
    try:
        return mem.publish_policy_fact(rule.label, rule.display, rule.source_url,
                                       rule.verified_date)
    except Exception as exc:  # noqa: BLE001
        log.info("policy_history seed failed for %s: %s", rule.id, type(exc).__name__)
        return None


def current(question: str) -> dict:
    """Recall the current value of a figure, with provenance. Returns a small dict the app and the
    drift checker can both use: {available, answer, provenance}. Safe when memory is unconfigured."""
    if not available():
        return {"available": False, "answer": None, "provenance": None}
    try:
        resp = mem.recall(question)
    except Exception as exc:  # noqa: BLE001
        log.info("policy_history recall failed: %s", type(exc).__name__)
        return {"available": True, "answer": None, "provenance": None, "error": type(exc).__name__}
    text = _current_fact(resp)
    return {"available": True, "answer": resp.get("answer") or text, "provenance": text,
            "tier": resp.get("tier")}


def _current_fact(resp: dict) -> str:
    """The most recent fact text. Facts are superseded, not overwritten, so newest = current."""
    chunks = [h for h in resp.get("hits", []) if h.get("source") == "memory_chunk"]
    if chunks:
        chunks.sort(key=lambda h: h.get("occurredAt", ""), reverse=True)
        return chunks[0].get("text", "")
    hits = resp.get("hits", [])
    return hits[0].get("text", "") if hits else ""


def _format_value(v: float) -> str:
    if 0 < v < 1:
        return f"{v * 100:g}%"
    if v >= 100:
        return f"${v:,.0f}"
    return f"{v:g}"
