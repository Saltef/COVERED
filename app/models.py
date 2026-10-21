"""Domain types (pure dataclasses, stdlib-only).

These carry NO persistence and NO PII beyond what a screening needs. Kept dependency-free
so the domain/ layer and the offline demo run on a bare Python install.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MaritalStatus(str, Enum):
    single = "single"
    married = "married"
    common_law = "common_law"
    widowed = "widowed"
    divorced = "divorced"
    separated = "separated"


class Eligibility(str, Enum):
    eligible = "eligible"          # rules met
    likely = "likely"             # rules met, pending a document/confirmation
    maybe = "maybe"               # plausible, needs more info / an application step
    not_eligible = "not_eligible"


@dataclass
class Profile:
    """A person's screening profile. PII is minimized; first name only, no address/SIN."""
    first_name: str = ""
    province: str = "ON"
    age: int = 0
    marital_status: MaritalStatus = MaritalStatus.single
    annual_net_income: float = 0.0
    family_net_income: Optional[float] = None       # adjusted family net income, if different
    has_private_dental_insurance: bool = False
    out_of_pocket_medical_annual: float = 0.0
    prescription_costs_annual: float = 0.0
    has_severe_prolonged_impairment: bool = False
    has_dtc_certificate: bool = False
    is_caregiver: bool = False
    filed_taxes_last_year: bool = True
    canadian_resident: bool = True

    def adjusted_family_net_income(self) -> float:
        return self.family_net_income if self.family_net_income is not None else self.annual_net_income


@dataclass
class ProgramResult:
    program_id: str
    program_name: str
    jurisdiction: str
    eligibility: Eligibility
    confidence: float
    estimated_annual_value: Optional[float]
    reasons: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    unlocked_by: Optional[str] = None          # e.g. "dtc" when gated by the DTC unlock chain
    value_is_illustrative: bool = True         # see PLAN.md task V1
