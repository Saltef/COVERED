"""Screening orchestration: run every program's rule, then apply the unlock graph."""
from __future__ import annotations

from app.domain.programs import PROGRAMS
from app.domain.unlock_graph import apply_unlocks
from app.models import Eligibility, Profile, ProgramResult

VALUE_ELIGIBILITIES = (Eligibility.eligible, Eligibility.likely, Eligibility.maybe)


def screen(profile: Profile) -> list[ProgramResult]:
    results = [prog.evaluate(profile) for prog in PROGRAMS]
    by_id = {r.program_id: r for r in results}
    apply_unlocks(by_id)
    return list(by_id.values())


def summarize(results: list[ProgramResult]) -> dict:
    claimable = [r for r in results if r.eligibility in VALUE_ELIGIBILITIES]
    with_value = [r for r in claimable if r.estimated_annual_value]
    return {
        "total_estimated_annual": sum(r.estimated_annual_value or 0 for r in with_value),
        "programs_with_value": len(with_value),
        "n_eligible_or_maybe": len(claimable),
        "all_values_illustrative": True,  # PLAN.md V1
    }
