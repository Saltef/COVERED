"""Catalogue builder logic, offline. The live enumeration (Cohere + network) is exercised by
scripts/build_catalogue.py; here we mock it and pin the grounding guard and the dedupe."""
from __future__ import annotations

from app.ops import catalogue_builder as cb


def test_grounded_drops_invented_names():
    text = "Ontario Health atHome arranges home care. The Assistive Devices Program funds equipment."
    assert cb._grounded("Ontario Health atHome", text) is True
    assert cb._grounded("Made Up Benefit", text) is False


def test_build_grounds_filters_and_classifies(monkeypatch):
    page = ("The Assistive Devices Program funds equipment. Ontario Health atHome arranges care. "
            "The Appeals Board hears appeals.")
    monkeypatch.setattr(cb, "_fetch_text", lambda url, cap=9000: page)
    monkeypatch.setattr(cb, "_client", lambda: object())
    monkeypatch.setattr(cb, "_enumerate", lambda c, t: [
        {"name": "Assistive Devices Program", "for_whom": "equipment", "how_to_apply": "ontario.ca"},
        {"name": "Ontario Health atHome", "for_whom": "home care", "how_to_apply": "call"},
        {"name": "Appeals Board", "for_whom": "appeals", "how_to_apply": "y"},   # grounded but off-topic
        {"name": "Phantom Program", "for_whom": "x", "how_to_apply": "y"},       # not on the page
    ])
    monkeypatch.setattr(cb, "_relevant", lambda c, n, f: "Appeals" not in n)
    monkeypatch.setattr(cb, "_classify",
                        lambda c, name, t: "rule-based" if "Assistive" in name else "assessment-based")
    names = {p.name for p in cb.build(sources=["http://x"])}
    assert "Assistive Devices Program" in names and "Ontario Health atHome" in names
    assert "Appeals Board" not in names    # dropped: off-topic
    assert "Phantom Program" not in names  # dropped: not grounded on the page
