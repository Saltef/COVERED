"""SurrealDB connectivity.

Day-1: the /screen flow is stateless, so the database is not required to run. This module
provides a degradation-safe status check (used by /healthz) and a connection helper that
loads the row-level-security schema. Full persistence is wired in Milestone 3.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import get_settings

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.surql")


async def surreal_status() -> str:
    """Never raises — returns a short status string for health reporting."""
    settings = get_settings()
    try:
        from surrealdb import Surreal  # noqa: F401  (lazy; optional dependency)
    except Exception:
        return "client-not-installed"
    try:
        db = Surreal(settings.surreal_url)
        await db.connect()
        await db.signin({"username": settings.surreal_user, "password": settings.surreal_pass})
        await db.close()
        return "connected"
    except Exception as exc:  # noqa: BLE001
        log.info("SurrealDB not reachable: %s", type(exc).__name__)
        return "unreachable"


def schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")
