"""Hand-labeled ground-truth cases for benchmarking the screening agent.

Each case lists the programs that SHOULD be actionable (eligible / likely / maybe) for that
person, derived independently from the real program rules. The benchmark checks the engine's
decisions against these labels — catching policy regressions and over/under-claiming.
"""
from __future__ import annotations

# program ids: dtc, cdb, cdcp, metc, ccc, rdsp, otdp
CASES: list[dict] = [
    {
        "id": "senior_margaret",  # low-income senior, impairment, high drug/medical costs
        "profile": {"province": "ON", "age": 71, "annual_net_income": 28_500,
                    "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 3_500,
                    "prescription_costs_annual": 1_800, "has_severe_prolonged_impairment": True},
        "expected_actionable": {"dtc", "cdcp", "metc", "otdp"},
    },
    {
        "id": "senior_low_need",  # senior, no impairment, low medical/drug spend
        "profile": {"province": "ON", "age": 68, "annual_net_income": 30_000,
                    "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 200,
                    "prescription_costs_annual": 100},
        "expected_actionable": {"cdcp", "otdp"},
    },
    {
        "id": "senior_high_income",  # over CDCP cap, no drug costs -> nothing
        "profile": {"province": "ON", "age": 70, "annual_net_income": 95_000,
                    "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 0,
                    "prescription_costs_annual": 0},
        "expected_actionable": set(),
    },
    {
        "id": "young_dtc_lowincome",  # 45, DTC certified, low income -> CDB + RDSP unlock
        "profile": {"province": "ON", "age": 45, "annual_net_income": 18_000,
                    "has_private_dental_insurance": False, "has_dtc_certificate": True,
                    "has_severe_prolonged_impairment": True, "prescription_costs_annual": 0},
        "expected_actionable": {"dtc", "cdb", "cdcp", "rdsp"},
    },
    {
        "id": "young_dtc_highincome",  # DTC but high income + private insurance
        "profile": {"province": "ON", "age": 50, "annual_net_income": 120_000,
                    "has_private_dental_insurance": True, "has_dtc_certificate": True,
                    "has_severe_prolonged_impairment": True, "prescription_costs_annual": 0},
        "expected_actionable": {"dtc", "cdb", "rdsp"},
    },
    {
        "id": "senior_insured_highcosts",  # has dental insurance (no CDCP) but high medical/drug costs
        "profile": {"province": "ON", "age": 72, "annual_net_income": 25_000,
                    "has_private_dental_insurance": True, "out_of_pocket_medical_annual": 4_000,
                    "prescription_costs_annual": 2_000},
        "expected_actionable": {"metc", "otdp"},
    },
    {
        "id": "bc_senior",  # British Columbia -> no Trillium
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
        "id": "child",  # under 18 -> CDCP child route
        "profile": {"province": "ON", "age": 10, "annual_net_income": 40_000,
                    "has_private_dental_insurance": False, "prescription_costs_annual": 0},
        "expected_actionable": {"cdcp"},
    },
    {
        "id": "uninsured_adult_no_dtc",  # 45, uninsured, no DTC -> CDCP (open to all ages since May 2025)
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
