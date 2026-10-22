"""Pytest fixtures. The TestClient is created as a context manager so the app's lifespan runs
(init_schema), which no-ops cleanly when SurrealDB is down."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
