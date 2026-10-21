"""Async REST client for the Era-simulated HubSpot systems (read-only).

Reads HUBSPOT_BASE_URL / HUBSPOT_MCP_HEADER from the environment (written by the `era` CLI).
Pages through all records so aggregates are exact.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx


def _conn() -> Optional[tuple[str, dict]]:
    from app.eval.era import _ensure_env
    _ensure_env()
    base = os.environ.get("HUBSPOT_BASE_URL", "").rstrip("/")
    header = os.environ.get("HUBSPOT_MCP_HEADER", "")
    if not base:
        return None
    headers = {}
    if ":" in header:
        name, value = header.split(":", 1)
        headers = {name.strip(): value.strip()}
    return base, headers


def configured() -> bool:
    return _conn() is not None


async def list_all(object_type: str, properties: Optional[list[str]] = None, cap: int = 2000) -> list[dict]:
    """Return every record of a CRM object (contacts/companies/deals/tickets), paging to `cap`."""
    conn = _conn()
    if conn is None:
        return []
    base, headers = conn
    out: list[dict] = []
    after: Optional[str] = None
    async with httpx.AsyncClient(timeout=30) as client:
        while len(out) < cap:
            params: dict = {"limit": 100}
            if properties:
                params["properties"] = ",".join(properties)
            if after:
                params["after"] = after
            resp = await client.get(f"{base}/crm/v3/objects/{object_type}", headers=headers, params=params)
            resp.raise_for_status()
            body = resp.json()
            out.extend(body.get("results", []))
            after = ((body.get("paging") or {}).get("next") or {}).get("after")
            if not after:
                break
    return out


async def get(object_type: str, record_id: str, properties: Optional[list[str]] = None) -> Optional[dict]:
    conn = _conn()
    if conn is None:
        return None
    base, headers = conn
    params = {"properties": ",".join(properties)} if properties else {}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{base}/crm/v3/objects/{object_type}/{record_id}", headers=headers, params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
