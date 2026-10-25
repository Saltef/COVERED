"""SurrealDB Agent Memory (Spectron): a time-aware, traceable store for POLICY facts.

Only public policy facts go here: figures from canada.ca / ontario.ca with their source and quote.
Never user, health, or income data (that stays in our own SurrealDB, under PHIPA). Each reading is
a fact with provenance; a changed value supersedes the prior one (the service infers this), and the
drift checker's generator and verifier agents share the same memory.

Degrades gracefully: with no SPECTRON_* configured, available() is False and callers no-op.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import get_settings

log = logging.getLogger(__name__)

SCOPE = "policy"  # all policy facts live under one scope


def available() -> bool:
    s = get_settings()
    return bool(s.spectron_url and s.spectron_context_id and s.spectron_api_key)


def _conn() -> tuple[str, str, dict]:
    s = get_settings()
    headers = {"Authorization": f"Bearer {s.spectron_api_key}", "Content-Type": "application/json"}
    return s.spectron_url.rstrip("/"), s.spectron_context_id, headers


def remember(text: str, scopes: Optional[list[str]] = None) -> dict:
    """Write a fact. `infer: full` lets the service supersede related prior facts."""
    url, ctx, headers = _conn()
    import httpx
    body: dict = {"text": text, "infer": "full"}
    if scopes:
        body["scopes"] = scopes
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{url}/api/v1/{ctx}/facts", headers=headers, json=body)
        r.raise_for_status()
        return r.json()


def recall(query: str, lens: Optional[list[str]] = None) -> dict:
    """Query the memory. Returns the grounded answer with its provenance."""
    url, ctx, headers = _conn()
    import httpx
    body: dict = {"query": query}
    if lens:
        body["lens"] = lens
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{url}/api/v1/{ctx}/query", headers=headers, json=body)
        r.raise_for_status()
        return r.json()


def publish_policy_fact(label: str, display: str, source_url: str, verified_date: str,
                        quote: str = "") -> dict:
    """Write one policy figure as a fact with full provenance. A changed value supersedes the prior
    fact for the same figure (the service infers the entity and supersession)."""
    text = f"As of {verified_date}, {label} is {display}. Source: {source_url}."
    if quote:
        text += f' Quote: "{quote}"'
    return remember(text)


def register_scope(path: str = SCOPE) -> dict:
    """Register a scope path (writes that use scopes require it). Idempotent-ish; ignores 409."""
    url, ctx, headers = _conn()
    import httpx
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{url}/api/v1/{ctx}/scopes", headers=headers, json={"path": path})
        if r.status_code not in (200, 201, 409):
            r.raise_for_status()
        return {"status": r.status_code}
