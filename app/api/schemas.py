"""Request/response models for the HTTP API (separate from the pure domain dataclasses)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.models import MaritalStatus, Profile, ProgramResult


class ProfileIn(BaseModel):
    first_name: str = ""
    province: str = "ON"
    age: int = 0
    marital_status: MaritalStatus = MaritalStatus.single
    annual_net_income: float = 0.0
    family_net_income: Optional[float] = None
    has_private_dental_insurance: bool = False
    out_of_pocket_medical_annual: float = 0.0
    prescription_costs_annual: float = 0.0
    has_severe_prolonged_impairment: bool = False
    has_dtc_certificate: bool = False
    is_caregiver: bool = False
    filed_taxes_last_year: bool = True
    canadian_resident: bool = True

    def to_domain(self) -> Profile:
        return Profile(**self.model_dump())


class ProgramResultOut(BaseModel):
    program_id: str
    program_name: str
    jurisdiction: str
    eligibility: str
    confidence: float
    estimated_annual_value: Optional[float]
    reasons: list[str]
    next_steps: list[str]
    unlocked_by: Optional[str]
    value_is_illustrative: bool

    @classmethod
    def from_domain(cls, r: ProgramResult) -> "ProgramResultOut":
        return cls(
            program_id=r.program_id,
            program_name=r.program_name,
            jurisdiction=r.jurisdiction,
            eligibility=r.eligibility.value,
            confidence=r.confidence,
            estimated_annual_value=r.estimated_annual_value,
            reasons=r.reasons,
            next_steps=r.next_steps,
            unlocked_by=r.unlocked_by,
            value_is_illustrative=r.value_is_illustrative,
        )


class ScreenResponse(BaseModel):
    headline: str
    summary: dict
    results: list[ProgramResultOut]
    explanation: Optional[str] = None
