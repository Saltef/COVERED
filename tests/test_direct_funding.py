"""Direct Funding eligibility + budget (deterministic, no dependencies).

Pins the real Ontario Reg 367/94 gates and the guide's budget formula so a rules change is caught.
"""
from __future__ import annotations

from app.domain import direct_funding as df

ELIGIBLE = dict(age=68, ontario_resident=True, has_ohip=True, permanent_physical_disability=True,
                tasks=["bathing", "dressing", "household"], needs_stable_1yr=True, can_self_manage=True)


def test_eligible_self_manager_is_likely():
    r = df.screen(**ELIGIBLE, hours_per_week=20)
    assert r.eligibility == "likely"
    assert r.monthly_budget and r.monthly_budget > 0


def test_unsure_self_manage_is_maybe():
    assert df.screen(**{**ELIGIBLE, "can_self_manage": False}).eligibility == "maybe"


def test_requires_a_hands_on_task():
    # two tasks, but neither is a core hands-on task
    assert df.screen(**{**ELIGIBLE, "tasks": ["household", "eating"]}).eligibility == "not_eligible"


def test_requires_at_least_two_tasks():
    assert df.screen(**{**ELIGIBLE, "tasks": ["bathing"]}).eligibility == "not_eligible"


def test_hard_gates_block():
    for override in ({"age": 15}, {"ontario_resident": False}, {"has_ohip": False},
                     {"permanent_physical_disability": False}, {"needs_stable_1yr": False}):
        assert df.screen(**{**ELIGIBLE, **override}).eligibility == "not_eligible"


def test_budget_uses_real_rates_and_cap():
    b = df.estimate_budget(100)  # 433 hrs/month -> capped at the 212.2 monthly maximum
    assert b["monthly_hours"] == df.MAX_HOURS_MONTH
    assert b["capped"] is True
    assert b["wages"] == round(df.MAX_HOURS_MONTH * df.WAGE)
    assert b["mercs"] == round(b["wages"] * df.MERC_RATE)
