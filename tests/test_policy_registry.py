"""The registry is the single source of truth for each eligibility figure. These tests lock the
engine's constants to it, so a change in one without the other fails the build. This is the
deterministic side of the engine-AI loop; the Cohere checker is the policy side."""
from __future__ import annotations

from app.domain import direct_funding as df
from app.domain import programs as p
from app.domain.policy_registry import REGISTRY

# registry id -> the engine constant it must equal
ENGINE = {
    "cdcp_income_cap": p.CDCP_INCOME_CAP,
    "cdcp_copay_tier1_cap": p.CDCP_COPAY_TIERS[0][0],
    "cdcp_copay_tier2_cap": p.CDCP_COPAY_TIERS[1][0],
    "metc_threshold": p.METC_FIXED_THRESHOLD,
    "metc_federal_rate": p.METC_FEDERAL_RATE,
    "cdb_max_annual": p.CDB_MAX_ANNUAL,
    "cdb_threshold_single": p.CDB_THRESHOLD_SINGLE,
    "cdb_threshold_partnered": p.CDB_THRESHOLD_PARTNERED,
    "cdb_reduction_rate": p.CDB_REDUCTION_RATE,
    "dtc_disability_amount": p.DTC_DISABILITY_AMOUNT,
    "df_wage": df.WAGE,
    "df_max_hours_month": df.MAX_HOURS_MONTH,
    "odb_min_age": p.ODB_MIN_AGE,
    "ohip_plus_max_age": p.OHIP_PLUS_MAX_AGE,
    "adp_coverage": p.ADP_COVERAGE,
}


def test_registry_matches_engine_constants():
    by_id = {r.id: r for r in REGISTRY}
    for rid, engine_value in ENGINE.items():
        assert rid in by_id, f"registry is missing {rid}"
        assert by_id[rid].value == engine_value, \
            f"{rid}: registry {by_id[rid].value} != engine {engine_value}"


def test_no_orphan_registry_entries():
    assert {r.id for r in REGISTRY} == set(ENGINE), "every registry entry must be checked against the engine"


def test_checkable_entries_have_query_and_source():
    for r in REGISTRY:
        if r.checkable:
            assert r.query, f"{r.id} is checkable but has no query"
            assert r.source_url.startswith("https://"), f"{r.id} has no source URL"
