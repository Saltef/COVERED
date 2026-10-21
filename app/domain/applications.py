"""The 'apply' step: map a profile onto real application forms.

We pre-fill every field we can safely derive, and clearly flag what the applicant must still
add (sensitive IDs we deliberately don't collect) and what a medical practitioner must complete.
This 'filled what we can, flagged the rest' design IS the ethics stance: we prepare, a human submits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from app.domain.programs import (
    CDCP_INCOME_CAP,
    METC_FEDERAL_RATE,
    METC_FIXED_THRESHOLD,
    trillium_deductible,
)
from app.models import Profile

# who completes a field
PREFILLED = "prefilled"       # Covered filled it from the interview
APPLICANT = "applicant"       # the person must add it (e.g. SIN, address)
PRACTITIONER = "practitioner"  # a medical practitioner must complete it


@dataclass
class FormField:
    label: str
    value: Optional[str]   # None => to be completed
    who: str = PREFILLED


@dataclass
class ApplicationPackage:
    program_id: str
    program_name: str
    form_name: str
    fields: list[FormField] = field(default_factory=list)
    still_needed: list[str] = field(default_factory=list)
    submission: list[str] = field(default_factory=list)
    status: str = "ready_to_review"


def _m(v: float) -> str:
    return f"${v:,.0f}"


def _yn(b: bool) -> str:
    return "Yes" if b else "No"


# ---- builders ------------------------------------------------------------

def build_t2201(p: Profile) -> ApplicationPackage:
    return ApplicationPackage(
        program_id="dtc",
        program_name="Disability Tax Credit",
        form_name="Form T2201 — Disability Tax Credit Certificate (Part A)",
        fields=[
            FormField("First name", p.first_name or None),
            FormField("Last name", None, APPLICANT),
            FormField("Province / territory", p.province),
            FormField("Social insurance number", None, APPLICANT),
            FormField("Date of birth", None, APPLICANT),
            FormField("Mailing address", None, APPLICANT),
            FormField("Applying for", "Myself"),
            FormField("Severe and prolonged impairment", _yn(p.has_severe_prolonged_impairment)),
            FormField("Part B — medical practitioner's certification", None, PRACTITIONER),
        ],
        still_needed=[
            "Add your last name, SIN, date of birth and mailing address.",
            "Sign and date Part A.",
            "Have your doctor or nurse practitioner complete and sign Part B.",
        ],
        submission=[
            "Submit to the CRA through My Account (‘Submit documents’) or mail it to your tax centre.",
            "Processing typically takes several weeks. Once approved, the DTC unlocks other programs.",
        ],
    )


def build_cdcp(p: Profile) -> ApplicationPackage:
    afni = p.adjusted_family_net_income()
    return ApplicationPackage(
        program_id="cdcp",
        program_name="Canadian Dental Care Plan",
        form_name="Canadian Dental Care Plan — Application Summary",
        fields=[
            FormField("First name", p.first_name or None),
            FormField("Last name", None, APPLICANT),
            FormField("Province / territory", p.province),
            FormField("Age", str(p.age)),
            FormField("No private/workplace dental insurance", _yn(not p.has_private_dental_insurance)),
            FormField(f"Adjusted family net income under {_m(CDCP_INCOME_CAP)}",
                      f"Yes (~{_m(afni)})"),
            FormField("Filed last year's tax return", _yn(p.filed_taxes_last_year)),
            FormField("Social insurance number", None, APPLICANT),
            FormField("Mailing address", None, APPLICANT),
        ],
        still_needed=[
            "Add your last name, SIN and mailing address.",
            "Confirm you still have no access to private dental coverage.",
        ],
        submission=[
            "Apply online at canada.ca/dental, or call Service Canada at 1-833-537-4342.",
            "Renew every year (the 2026 renewal window is Apr 15 – Jun 1).",
        ],
    )


def build_metc(p: Profile) -> ApplicationPackage:
    threshold = min(0.03 * p.annual_net_income, METC_FIXED_THRESHOLD)
    excess = max(p.out_of_pocket_medical_annual - threshold, 0)
    credit = round(METC_FEDERAL_RATE * excess)
    return ApplicationPackage(
        program_id="metc",
        program_name="Medical Expense Tax Credit",
        form_name="Medical Expense Tax Credit — Claim Worksheet (line 33099)",
        fields=[
            FormField("Net income", _m(p.annual_net_income)),
            FormField("Total eligible medical expenses", _m(p.out_of_pocket_medical_annual)),
            FormField("Threshold (lesser of 3% of net income or " + _m(METC_FIXED_THRESHOLD) + ")",
                      _m(threshold)),
            FormField("Claimable amount (expenses − threshold)", _m(excess)),
            FormField(f"Estimated federal credit ({int(METC_FEDERAL_RATE*100)}%)", _m(credit)),
            FormField("Return line", "33099"),
        ],
        still_needed=[
            "Gather and total all medical receipts for the year.",
            "Keep every receipt for at least 6 years in case the CRA asks.",
        ],
        submission=[
            "Enter the claimable amount on line 33099 of your T1 return.",
            "Your tax software or preparer applies the credit automatically.",
        ],
    )


def build_trillium(p: Profile) -> ApplicationPackage:
    deductible = trillium_deductible(p.annual_net_income)
    return ApplicationPackage(
        program_id="otdp",
        program_name="Ontario Trillium Drug Program",
        form_name="Ontario Trillium Drug Program — Application Summary",
        fields=[
            FormField("First name", p.first_name or None),
            FormField("Last name", None, APPLICANT),
            FormField("Province", p.province),
            FormField("Annual prescription costs", _m(p.prescription_costs_annual)),
            FormField("Household net income", _m(p.annual_net_income)),
            FormField("Estimated annual deductible (income-tested)", _m(deductible)),
            FormField("Ontario health card number", None, APPLICANT),
        ],
        still_needed=[
            "Add your last name and Ontario health card number.",
            "Attach proof of income (e.g. Notice of Assessment).",
        ],
        submission=[
            "Get the enrolment form at your pharmacy or from ServiceOntario.",
            "Submit the completed form with proof of income to the Trillium Drug Program.",
        ],
    )


BUILDERS: dict[str, Callable[[Profile], ApplicationPackage]] = {
    "dtc": build_t2201,
    "cdcp": build_cdcp,
    "metc": build_metc,
    "otdp": build_trillium,
}

_ACTIONABLE = ("eligible", "likely", "maybe")


def build_packages(profile: Profile, results: list) -> list[ApplicationPackage]:
    out: list[ApplicationPackage] = []
    for r in results:
        if r.eligibility.value in _ACTIONABLE and r.program_id in BUILDERS:
            out.append(BUILDERS[r.program_id](profile))
    return out


def get_package(program_id: str, profile: Profile) -> Optional[ApplicationPackage]:
    builder = BUILDERS.get(program_id)
    return builder(profile) if builder else None


def build_partb_context(profile: dict) -> dict:
    """What a clinician sees to complete T2201 Part B. Covered pre-fills identity + the patient's
    self-reported status; the doctor completes the clinical sections and submits in CRA's portal."""
    return {
        "patient_first_name": profile.get("first_name") or "",
        "province": profile.get("province"),
        "self_reported": ("Patient reports a severe and prolonged impairment."
                          if profile.get("has_severe_prolonged_impairment")
                          else "No impairment reported by the patient."),
        "sections_to_complete": [
            "Nature of the impairment (vision, speaking, hearing, walking, eliminating, feeding, "
            "dressing, mental functions, or life-sustaining therapy).",
            "Effects of the impairment on everyday activities.",
            "When it began and whether it is prolonged (12+ months).",
            "Your profession and how long you have been the patient's practitioner.",
            "Certification and signature.",
        ],
        "handoff": ("Covered pre-fills the patient's identity and self-reported status. You complete "
                    "the clinical Part B and submit it in CRA's portal using the reference number."),
    }


def package_to_dict(pkg: ApplicationPackage) -> dict:
    return {
        "program_id": pkg.program_id,
        "program_name": pkg.program_name,
        "form_name": pkg.form_name,
        "fields": [{"label": f.label, "value": f.value, "who": f.who} for f in pkg.fields],
        "still_needed": pkg.still_needed,
        "submission": pkg.submission,
        "status": pkg.status,
    }
