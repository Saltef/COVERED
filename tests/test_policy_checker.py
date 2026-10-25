"""The drift checker's classification logic, offline. The live extraction (Cohere + network) is
exercised by scripts/check_policy_drift.py, not here; these tests mock it and pin match /
mismatch / unverified / fetch-failure."""
from __future__ import annotations

from app.domain.policy_registry import REGISTRY
from app.ops import policy_checker as pc


def _rule():
    return next(r for r in REGISTRY if r.id == "cdcp_income_cap")  # value 90000


def test_match(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_passages", lambda url: ["x"])
    monkeypatch.setattr(pc, "_extract", lambda c, r, passages: (90000, "income less than $90,000"))
    res = pc.check_rule(_rule(), client=object())
    assert res.status == "match" and res.extracted_value == 90000


def test_mismatch(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_passages", lambda url: ["x"])
    monkeypatch.setattr(pc, "_extract", lambda c, r, passages: (80000, "income less than $80,000"))
    assert pc.check_rule(_rule(), client=object()).status == "mismatch"


def test_unverified_when_no_value(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_passages", lambda url: ["x"])
    monkeypatch.setattr(pc, "_extract", lambda c, r, passages: (None, ""))
    assert pc.check_rule(_rule(), client=object()).status == "unverified"


def test_unverified_on_fetch_failure(monkeypatch):
    def boom(url):
        raise RuntimeError("network down")
    monkeypatch.setattr(pc, "_fetch_passages", boom)
    assert pc.check_rule(_rule(), client=object()).status == "unverified"
