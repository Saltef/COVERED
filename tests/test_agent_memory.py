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
