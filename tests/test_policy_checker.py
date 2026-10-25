"""The drift checker's classification logic, offline. The live extraction (Cohere + network) is
exercised by scripts/check_policy_drift.py, not here; these tests mock it and pin match /
mismatch / unverified / fetch-failure."""
from __future__ import annotations

from app.domain.policy_registry import REGISTRY
from app.ops import policy_checker as pc


def _rule():
    return next(r for r in REGISTRY if r.id == "cdcp_income_cap")  # value 90000


def _agrees(c, r, value, quote, top):
    return {"agrees": True, "current_period": True, "conflicting_value": None, "reason": "ok"}


def test_match_when_verifier_agrees(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_passages", lambda url: ["x"])
    monkeypatch.setattr(pc, "_rerank_top", lambda c, q, p, top_n=5: p)
    monkeypatch.setattr(pc, "_extract", lambda c, r, top: (90000, "income less than $90,000"))
    monkeypatch.setattr(pc, "_verify", _agrees)
    res = pc.check_rule(_rule(), client=object())
    assert res.status == "match" and res.extracted_value == 90000 and res.confidence == "high"


def test_mismatch_when_verifier_agrees(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_passages", lambda url: ["x"])
    monkeypatch.setattr(pc, "_rerank_top", lambda c, q, p, top_n=5: p)
    monkeypatch.setattr(pc, "_extract", lambda c, r, top: (80000, "income less than $80,000"))
    monkeypatch.setattr(pc, "_verify", _agrees)
    assert pc.check_rule(_rule(), client=object()).status == "mismatch"


def test_downgraded_when_verifier_disagrees(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_passages", lambda url: ["x"])
    monkeypatch.setattr(pc, "_rerank_top", lambda c, q, p, top_n=5: p)
    monkeypatch.setattr(pc, "_extract", lambda c, r, top: (90000, "income less than $90,000"))
    monkeypatch.setattr(pc, "_verify", lambda c, r, v, q, t: {"agrees": False, "reason": "not stated"})
    res = pc.check_rule(_rule(), client=object())
    assert res.status == "unverified" and res.confidence == "low"


def test_unverified_when_no_value(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_passages", lambda url: ["x"])
    monkeypatch.setattr(pc, "_rerank_top", lambda c, q, p, top_n=5: p)
    monkeypatch.setattr(pc, "_extract", lambda c, r, top: (None, ""))
    assert pc.check_rule(_rule(), client=object()).status == "unverified"


def test_unverified_on_fetch_failure(monkeypatch):
    def boom(url):
        raise RuntimeError("network down")
    monkeypatch.setattr(pc, "_fetch_passages", boom)
    assert pc.check_rule(_rule(), client=object()).status == "unverified"
