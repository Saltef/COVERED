"""Hand-labeled regression cases for the screening engine.

Each case lists the programs that SHOULD be actionable (eligible / likely / maybe) for that
person. The labels are hand-derived from the same program rules the engine encodes, by the same
team, so a pass measures regression-stability and internal consistency, NOT that the eligibility
logic matches reality. The external accuracy check (engine figures vs official government sources)
is the policy drift checker (scripts/check_policy_drift.py). This suite catches policy regressions
and over/under-claiming across income caps, province gating, age bands, and the do-not-over-claim
case.

Drug-coverage age bands: under 25 = OHIP+, 25-64 = Trillium (if high rx cost), 65+ = Ontario Drug
Benefit. Ontario programs (otdp, odb, ohipplus, adp) never fire outside Ontario.
"""
from __future__ import annotations

# program ids: dtc, cdb, cdcp, metc, ccc, rdsp, otdp, odb, ohipplus, adp
CASES: list[dict] = [
    {
        "id": "senior_margaret",  # low-income senior, impairment, high drug/medical costs
        "profile": {"province": "ON", "age": 71, "annual_net_income": 28_500,
                    "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 3_500,
                    "prescription_costs_annual": 1_800, "has_severe_prolonged_impairment": True},
        "expected_actionable": {"dtc", "cdcp", "metc", "odb", "adp"},
    },
    {
        "id": "senior_low_need",  # senior, no impairment, low spend
        "profile": {"province": "ON", "age": 68, "annual_net_income": 30_000,
                    "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 200,
                    "prescription_costs_annual": 100},
        "expected_actionable": {"cdcp", "odb"},
    },
    {
        "id": "senior_high_income",  # 65+ gets ODB automatically regardless of income
        "profile": {"province": "ON", "age": 70, "annual_net_income": 95_000,
                    "has_private_dental_insurance": True, "out_of_pocket_medical_annual": 0,
                    "prescription_costs_annual": 0},
        "expected_actionable": {"odb"},
    },
    {
        "id": "young_dtc_lowincome",  # 45, DTC certified, low income -> unlock chain + ADP
        "profile": {"province": "ON", "age": 45, "annual_net_income": 18_000,
                    "has_private_dental_insurance": False, "has_dtc_certificate": True,
                    "has_severe_prolonged_impairment": True, "prescription_costs_annual": 0},
        "expected_actionable": {"dtc", "cdb", "cdcp", "rdsp", "adp"},
    },
    {
        "id": "young_dtc_highincome",  # DTC but high income + private insurance
        "profile": {"province": "ON", "age": 50, "annual_net_income": 120_000,
                    "has_private_dental_insurance": True, "has_dtc_certificate": True,
                    "has_severe_prolonged_impairment": True, "prescription_costs_annual": 0},
        "expected_actionable": {"dtc", "cdb", "rdsp", "adp"},
    },
    {
        "id": "senior_insured_highcosts",  # has dental insurance (no CDCP) but high medical costs
        "profile": {"province": "ON", "age": 72, "annual_net_income": 25_000,
                    "has_private_dental_insurance": True, "out_of_pocket_medical_annual": 4_000,
                    "prescription_costs_annual": 2_000},
        "expected_actionable": {"metc", "odb"},
    },
    {
        "id": "bc_senior",  # British Columbia -> no Ontario programs at all
        "profile": {"province": "BC", "age": 70, "annual_net_income": 20_000,
                    "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 3_000,
                    "prescription_costs_annual": 1_500, "has_severe_prolonged_impairment": True},
        "expected_actionable": {"dtc", "cdcp", "metc"},
    },
    {
        "id": "caregiver",  # supports a dependant with an impairment
        "profile": {"province": "ON", "age": 55, "annual_net_income": 60_000,
                    "has_private_dental_insurance": True, "is_caregiver": True,
                    "prescription_costs_annual": 0},
        "expected_actionable": {"ccc"},
    },
    {
        "id": "child_youth",  # under 18 -> CDCP child route + OHIP+ drug coverage
        "profile": {"province": "ON", "age": 10, "annual_net_income": 40_000,
                    "has_private_dental_insurance": False, "prescription_costs_annual": 0},
        "expected_actionable": {"cdcp", "ohipplus"},
    },
    {
        "id": "young_adult_rx",  # 22, high drug costs -> OHIP+ covers (not Trillium)
        "profile": {"province": "ON", "age": 22, "annual_net_income": 15_000,
                    "has_private_dental_insurance": False, "prescription_costs_annual": 1_200},
        "expected_actionable": {"cdcp", "ohipplus"},
    },
    {
        "id": "working_age_trillium",  # 50, high drug costs, no impairment -> Trillium band
        "profile": {"province": "ON", "age": 50, "annual_net_income": 24_000,
                    "has_private_dental_insurance": False, "prescription_costs_annual": 2_400},
        "expected_actionable": {"cdcp", "otdp"},
    },
    {
        "id": "uninsured_adult_no_dtc",  # 45, uninsured, no DTC -> CDCP only
        "profile": {"province": "ON", "age": 45, "annual_net_income": 35_000,
                    "has_private_dental_insurance": False, "prescription_costs_annual": 0},
        "expected_actionable": {"cdcp"},
    },
    {
        "id": "nothing",  # mid-income, insured, no impairment -> don't over-claim
        "profile": {"province": "ON", "age": 40, "annual_net_income": 70_000,
                    "has_private_dental_insurance": True, "prescription_costs_annual": 0},
        "expected_actionable": set(),
    },
]
