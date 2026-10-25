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
    illustrative = [r for r in with_value if r.value_is_illustrative]
    return {
        # dollar total only from programs where the amount is computed from the person's inputs
        "total_estimated_annual": sum(r.estimated_annual_value or 0 for r in with_value),
        "programs_with_value": len(with_value),
        "programs_coverage_only": len(claimable) - len(with_value),  # eligible but no fixed $ (e.g. CDCP)
        "n_eligible_or_maybe": len(claimable),
        "any_values_illustrative": bool(illustrative),
    }


def headline(summary: dict) -> str:
    """Honest headline: count the programs, state only the dollar total we can actually calculate,
    and note programs that provide coverage rather than a cash amount. No fabricated figure."""
    n = summary.get("n_eligible_or_maybe", 0)
    total = summary.get("total_estimated_annual", 0)
    cov = summary.get("programs_coverage_only", 0)
    h = f"You may qualify for {n} program{'' if n == 1 else 's'}."
    if total:
        h += f" Where the amount can be calculated, that is about ${total:,.0f} a year"
        h += f", plus coverage from {cov} more." if cov else "."
    elif cov:
        h += f" {cov} provide coverage (dental, equipment) rather than a cash amount."
    return h
