"""Layer 4 - graceful degradation when a dependency is down.

Each test takes one dependency away and asserts the surface degrades (falls back or reports
unavailable) instead of crashing. These mirror what scripts/preflight.py checks live.
"""
from __future__ import annotations

import asyncio

from app import llm
from app.agents.explainer import explain
from app.agents.voice import transcribe
from app.db import repository as repo
from tests._support import dev

SENIOR = {"first_name": "X", "province": "ON", "age": 71, "annual_net_income": 22000}


def test_screening_still_works_without_llm(client, monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    r = client.post("/screen", json=SENIOR, headers=dev("senior"))
    assert r.status_code == 200
    assert r.json()["explanation"]  # deterministic fallback text, not empty or an error


def test_explainer_falls_back_without_llm(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    text = asyncio.run(explain("You could be owed $1,000.", []))
    assert "confirm and submit" in text.lower()


def test_book_copilot_reports_unavailable_without_llm(client, monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    d = client.get("/ops/ask-book", params={"q": "how many clients"}, headers=dev("admin")).json()
    assert d["available"] is False


def test_voice_reports_unavailable_without_cohere(monkeypatch):
    import app.agents.voice as voice
    monkeypatch.setattr(voice, "get_settings", lambda: type("S", (), {"cohere_api_key": ""})())
    res = asyncio.run(transcribe(b"not audio"))
    assert res.available is False


def test_storage_down_returns_503(client, monkeypatch):
    async def boom(*a, **k):
        raise repo.SurrealUnavailable("down")
    monkeypatch.setattr(repo, "list_screenings", boom)
    assert client.get("/agency/caseload", headers=dev("admin")).status_code == 503
