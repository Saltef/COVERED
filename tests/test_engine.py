"""Layer 1 - rules engine matrix. Pure and deterministic, no dependencies.

The matrix is data-driven: ground_truth.CASES is the canonical table of
{profile, expected_actionable}. Add a row there to add a case. The targeted tests below pin one
eligibility branch each so a regression names the exact rule that broke.
"""
from __future__ import annotations

import pytest

from app.domain.programs import PROGRAMS
from app.domain.rules_engine import screen
from app.eval.benchmark import run
from app.eval.ground_truth import CASES
from app.models import Profile

ACTIONABLE = {"eligible", "likely", "maybe"}


def _actionable(profile: dict) -> set[str]:
    return {r.program_id for r in screen(Profile(**profile)) if r.eligibility.value in ACTIONABLE}


def _by_id(profile: dict) -> dict:
    return {r.program_id: r for r in screen(Profile(**profile))}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_ground_truth_case(case):
    assert _actionable(case["profile"]) == set(case["expected_actionable"])


def test_benchmark_is_perfect():
    r = run(None)
    assert r["cases_passed"] == r["n_cases"]
    assert r["decision_accuracy"] == 1.0


def test_every_program_is_evaluated():
    assert set(_by_id({"age": 70}).keys()) == {p.id for p in PROGRAMS}


def test_cdb_excluded_at_65():
    assert _by_id({"age": 70, "has_dtc_certificate": True, "annual_net_income": 18000})["cdb"].eligibility.value == "not_eligible"


def test_cdb_included_working_age_with_dtc():
    assert _by_id({"age": 45, "has_dtc_certificate": True, "annual_net_income": 18000})["cdb"].eligibility.value in ACTIONABLE


def test_rdsp_excluded_at_60():
    assert _by_id({"age": 61, "has_dtc_certificate": True})["rdsp"].eligibility.value == "not_eligible"


def test_cdcp_open_to_all_ages_without_dtc():
    assert _by_id({"age": 45, "has_private_dental_insurance": False, "annual_net_income": 35000})["cdcp"].eligibility.value == "eligible"


def test_cdcp_excluded_when_insured():
    assert _by_id({"age": 45, "has_private_dental_insurance": True, "annual_net_income": 35000})["cdcp"].eligibility.value == "not_eligible"


def test_cdcp_excluded_over_income_cap():
    assert _by_id({"age": 45, "has_private_dental_insurance": False, "annual_net_income": 95000})["cdcp"].eligibility.value == "not_eligible"


def test_trillium_only_in_ontario():
    base = {"prescription_costs_annual": 3000, "annual_net_income": 20000}
    assert _by_id({**base, "province": "ON"})["otdp"].eligibility.value == "eligible"
    assert _by_id({**base, "province": "BC"})["otdp"].eligibility.value == "not_eligible"


def test_dtc_certificate_is_high_confidence():
    r = _by_id({"has_dtc_certificate": True, "age": 50})["dtc"]
    assert r.eligibility.value == "eligible" and r.confidence >= 0.9
