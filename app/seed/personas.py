"""Synthetic personas. Not real people — safe to commit."""
from __future__ import annotations

from app.models import MaritalStatus, Profile


def sample_senior() -> Profile:
    """Low-income senior widow in Ontario — the anchor demo persona."""
    return Profile(
        first_name="Margaret",
        province="ON",
        age=71,
        marital_status=MaritalStatus.widowed,
        annual_net_income=28_500,
        family_net_income=28_500,
        has_private_dental_insurance=False,
        out_of_pocket_medical_annual=3_500,
        prescription_costs_annual=1_800,
        has_severe_prolonged_impairment=True,
        has_dtc_certificate=False,
        is_caregiver=False,
        filed_taxes_last_year=True,
        canadian_resident=True,
    )


PERSONAS = {"senior": sample_senior}
