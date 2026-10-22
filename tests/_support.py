"""Shared helpers: dev-identity headers, unique ids, and a SurrealDB skip marker.

See USE-CASES.md for the four-layer scheme. The engine matrix and most contract/resilience
tests need no database; journey and persistence tests are skipped when SurrealDB is unreachable.
"""
from __future__ import annotations

import asyncio
import os
import uuid

os.environ.setdefault("SURREAL_URL", "ws://localhost:8001/rpc")

import pytest

from app.db import repository as repo


def _surreal_up() -> bool:
    try:
        return asyncio.run(repo.ping()) == "connected"
    except Exception:
        return False


SURREAL_UP = _surreal_up()
requires_surreal = pytest.mark.skipif(not SURREAL_UP, reason="SurrealDB not reachable on SURREAL_URL")


def dev(role: str = "senior", user: str = "dev-user") -> dict:
    """Dev-identity headers (the app runs with header auth in development)."""
    return {"X-Dev-Role": role, "X-Dev-User": user}


def uniq(prefix: str = "u") -> str:
    """A fresh dev-user id so journey tests do not collide with seeded or each other's data."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
