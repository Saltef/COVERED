"""Document extraction: parsing, sanitization, and the privacy guards. The LLM is mocked, so these
run offline and pin the behaviour that matters: net income is read, a SIN is never returned, and a
stale year is flagged."""
from __future__ import annotations

import asyncio
import datetime as _dt
import types

from app.agents import extract


def _fake_vision(content: str):
    """Build a stand-in for llm.chat_vision returning `content` as the model's reply."""
    msg = types.SimpleNamespace(message=types.SimpleNamespace(content=content))
    return types.SimpleNamespace(choices=[msg])


def _run(image=b"x", ctype="image/png"):
    return asyncio.run(extract.extract_profile_fields(image, ctype))


def test_reads_net_income_and_year(monkeypatch):
    monkeypatch.setattr(extract.llm, "available", lambda: True)
    monkeypatch.setattr(extract.llm, "chat_vision",
                        lambda *a, **k: _fake_vision('{"net_income": 28500, "tax_year": 2024, "province": "ON"}'))
    out = _run()
    assert out["available"] is True
    assert out["fields"]["annual_net_income"] == 28500
    assert out["fields"]["province"] == "ON"
    assert out["tax_year"] == 2024
    assert "28,500" in out["read"]


def test_prefers_net_over_total_income(monkeypatch):
    monkeypatch.setattr(extract.llm, "available", lambda: True)
    monkeypatch.setattr(extract.llm, "chat_vision",
                        lambda *a, **k: _fake_vision('{"net_income": 30000, "total_income": 42000}'))
    out = _run()
    assert out["fields"]["annual_net_income"] == 30000  # net income wins


def test_sin_is_never_returned(monkeypatch):
    # A 9-digit value in the income slot is a SIN leaking in; it must be dropped, not used as income.
    monkeypatch.setattr(extract.llm, "available", lambda: True)
    monkeypatch.setattr(extract.llm, "chat_vision",
                        lambda *a, **k: _fake_vision('{"net_income": 123456789, "tax_year": 2024}'))
    out = _run()
    assert "annual_net_income" not in out["fields"]


def test_not_found_gives_helpful_read(monkeypatch):
    monkeypatch.setattr(extract.llm, "available", lambda: True)
    monkeypatch.setattr(extract.llm, "chat_vision", lambda *a, **k: _fake_vision("no json here"))
    out = _run()
    assert out["fields"] == {}
    assert "enter them yourself" in out["read"].lower()


def test_stale_year_is_flagged(monkeypatch):
    monkeypatch.setattr(extract.llm, "available", lambda: True)
    old = _dt.date.today().year - 5
    monkeypatch.setattr(extract.llm, "chat_vision",
                        lambda *a, **k: _fake_vision(f'{{"net_income": 20000, "tax_year": {old}}}'))
    out = _run()
    assert out["stale"] is True


def test_pdf_is_declined_with_guidance(monkeypatch):
    monkeypatch.setattr(extract.llm, "available", lambda: True)
    out = _run(ctype="application/pdf")
    assert out["fields"] == {}
    assert "photo" in out["detail"].lower()


def test_no_llm_degrades(monkeypatch):
    monkeypatch.setattr(extract.llm, "available", lambda: False)
    out = _run()
    assert out["available"] is False
