"""Agent Memory client request shaping, offline. The live writes/reads are exercised by
scripts/sync_policy_memory.py; here we mock httpx and pin the endpoint, auth, and body."""
from __future__ import annotations

import httpx

from app.ops import agent_memory as mem


class _Resp:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"turnId": "t", "hits": []}


def _fake_client(calls):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, url, headers=None, json=None):
            calls.append({"url": url, "headers": headers, "json": json})
            return _Resp()
    return FakeClient


def test_remember_posts_a_fact(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "Client", _fake_client(calls))
    mem.remember("CDCP cap is $90,000")
    assert calls[0]["url"].endswith("/facts")
    assert calls[0]["json"] == {"text": "CDCP cap is $90,000", "infer": "full"}
    assert calls[0]["headers"]["Authorization"].startswith("Bearer ")


def test_recall_posts_a_query(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "Client", _fake_client(calls))
    mem.recall("what is the cap?")
    assert calls[0]["url"].endswith("/query")
    assert calls[0]["json"]["query"] == "what is the cap?"


def test_publish_policy_fact_includes_provenance(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "Client", _fake_client(calls))
    mem.publish_policy_fact("CDCP income cap", "$90,000", "https://canada.ca/x", "2026-10-21",
                            quote="less than $90,000")
    text = calls[0]["json"]["text"]
    assert "$90,000" in text and "https://canada.ca/x" in text and "2026-10-21" in text
    assert "less than $90,000" in text  # the quote is carried as provenance


# ---- policy_history: the drift checker's shared, queryable memory ----
from dataclasses import dataclass

from app.ops import policy_history as hist


@dataclass
class _Res:
    id: str = "cdcp_income_cap"
    label: str = "CDCP income cap"
    engine_value: float = 90_000
    extracted_value: float | None = 90_000
    quote: str = "less than $90,000"
    status: str = "match"
    confidence: str = "high"


def test_record_check_noop_without_memory(monkeypatch):
    monkeypatch.setattr(hist, "available", lambda: False)
    assert hist.record_check(_Res()) is None  # degrades gracefully


def test_record_check_only_writes_confident_results(monkeypatch):
    written = []
    monkeypatch.setattr(hist, "available", lambda: True)
    monkeypatch.setattr(hist.mem, "publish_policy_fact",
                        lambda *a, **k: written.append((a, k)) or {"ok": True})
    # unverified / low-confidence results are not asserted as facts
    assert hist.record_check(_Res(status="unverified", confidence="low")) is None
    assert hist.record_check(_Res(extracted_value=None)) is None
    assert not written
    # a verifier-confident reading is written, with its source and quote
    hist.record_check(_Res(status="mismatch"), source_url="https://canada.ca/x")
    assert written and written[0][0][2] == "https://canada.ca/x"  # source_url passed through


def test_current_noop_without_memory(monkeypatch):
    monkeypatch.setattr(hist, "available", lambda: False)
    r = hist.current("what is the CDCP cap?")
    assert r == {"available": False, "answer": None, "provenance": None}


def test_current_fact_picks_newest(monkeypatch):
    monkeypatch.setattr(hist, "available", lambda: True)
    resp = {"hits": [
        {"source": "memory_chunk", "text": "old $23,000", "occurredAt": "2025-01-01"},
        {"source": "memory_chunk", "text": "new $23,483", "occurredAt": "2026-10-25"},
    ]}
    monkeypatch.setattr(hist.mem, "recall", lambda q: resp)
    assert "23,483" in hist.current("threshold?")["provenance"]
