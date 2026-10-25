"""Score the screening agent's eligibility decisions against ground-truth labels."""
from __future__ import annotations

from typing import Optional

from app.domain.rules_engine import screen
from app.eval.ground_truth import CASES
from app.models import Profile

ALL_PROGRAMS = ["dtc", "cdb", "cdcp", "metc", "ccc", "rdsp", "otdp", "odb", "ohipplus", "adp"]
_ACTIONABLE = {"eligible", "likely", "maybe"}


def _profile(d: dict) -> Profile:
    return Profile(**d)


def evaluate_case(case: dict) -> dict:
    results = {r.program_id: r for r in screen(_profile(case["profile"]))}
    expected = set(case["expected_actionable"])
    mismatches = []
    correct = 0
    for pid in ALL_PROGRAMS:
        got = results[pid].eligibility.value in _ACTIONABLE
        exp = pid in expected
        if got == exp:
            correct += 1
        else:
            mismatches.append({"program": pid, "got_actionable": got, "expected_actionable": exp})
    return {"id": case["id"], "correct": correct, "total": len(ALL_PROGRAMS),
            "passed": not mismatches, "mismatches": mismatches}


def run(cases: Optional[list[dict]] = None) -> dict:
    source = "builtin-ground-truth" if cases is None else "era-generated"
    cases = cases if cases is not None else CASES
    case_results = [evaluate_case(c) for c in cases]
    total_correct = sum(c["correct"] for c in case_results)
    total = sum(c["total"] for c in case_results)
    per_program_errors: dict[str, int] = {}
    for c in case_results:
        for m in c["mismatches"]:
            per_program_errors[m["program"]] = per_program_errors.get(m["program"], 0) + 1
    return {
        "source": source,
        "n_cases": len(case_results),
        "cases_passed": sum(1 for c in case_results if c["passed"]),
        "decision_accuracy": round(total_correct / total, 4) if total else 0.0,
        "correct_decisions": total_correct,
        "total_decisions": total,
        "per_program_errors": per_program_errors,
        "cases": case_results,
    }
