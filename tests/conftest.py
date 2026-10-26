"""Pytest fixtures. The TestClient is created as a context manager so the app's lifespan runs
(init_schema), which no-ops cleanly when SurrealDB is down."""
from __future__ import annotations

import os

# Isolate tests on an embedded, in-memory SurrealDB: persistence tests always run (locally and in
# CI) and never touch demo data. Set TEST_SURREAL_URL to test against a real server instead.
# Must run before app settings are first read.
os.environ["SURREAL_URL"] = os.environ.get("TEST_SURREAL_URL", "mem://")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
