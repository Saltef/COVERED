"""Benefit catalogue + deterministic eligibility rules.

Figures below re-verified against 2025/2026 official sources on 2026-10-21 (see the constants block).
Policy note: the Canadian Dental Care Plan is open to ALL ages since the May 2025 expansion (no DTC or
age route needed). A person's actual amount still depends on their situation.

Design rule: the ENGINE decides eligibility deterministically (auditable / reproducible).
Claude (agents layer) only phrases the "why" — it never decides eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models import Eligibility, Profile, ProgramResult

# ---- figures re-verified against 2025/2026 official sources (2026-10-21) ----
# Canadian Dental Care Plan: adjusted family net income under $90,000, no access to dental insurance,
# prior-year tax return filed, Canadian resident. Open to ALL ages since the May 2025 expansion (no
# DTC/age route). 0% co-pay under $70k, then tiered. Source: Health Canada / canada.ca/dental.
CDCP_INCOME_CAP = 90_000
# CDCP co-pay tiers: the % of the set fee the plan pays, by adjusted family net income. Source: Health
# Canada. The cash value depends on the dental work done, so we report the coverage %, not a made-up $.
CDCP_COPAY_TIERS = [(70_000, 100), (80_000, 60), (90_000, 40)]


def cdcp_coverage_pct(afni: float) -> int:
    for cap, pct in CDCP_COPAY_TIERS:
        if afni < cap:
            return pct
    return 0

# Medical Expense Tax Credit (2025): threshold = lesser of 3% of net income or $2,834,
# credited at the 15% federal rate. Source: CRA 2025.
METC_FIXED_THRESHOLD = 2_834
METC_FEDERAL_RATE = 0.15

# Disability Tax Credit (2025): base disability amount $10,138; federal value = 15% of it ≈ $1,521.
DTC_DISABILITY_AMOUNT = 10_138
DTC_FEDERAL_VALUE = round(METC_FEDERAL_RATE * DTC_DISABILITY_AMOUNT)

# Canada Disability Benefit (Jul 2026–Jun 2027): max $204.20/mo ($2,450/yr); reduced 20¢ per $ of
# adjusted family net income above the indexed thresholds. Source: ESDC.
CDB_MAX_ANNUAL = round(204.20 * 12)     # $2,450 (2026-27)
CDB_REDUCTION_RATE = 0.20
CDB_THRESHOLD_SINGLE = 23_483           # 2026-27 indexed
CDB_THRESHOLD_PARTNERED = 33_182

# Ontario Trillium Drug Program deductible (household net income < $100k):
# ~4.5% of (household net income − $20,000) + $500. Source: Ontario / Benefits Canada.
TRILLIUM_BASE_DEDUCTION = 20_000
TRILLIUM_RATE = 0.045
TRILLIUM_FLAT = 500


# Ontario Drug Benefit (ODB): automatic prescription coverage at 65+ in Ontario (small co-pay).
ODB_MIN_AGE = 65
# OHIP+: free prescription drugs for Ontarians under 25 without a private drug plan.
OHIP_PLUS_MAX_AGE = 25
# Assistive Devices Program (ADP): funds ~75% of approved equipment for a long-term physical disability.
ADP_COVERAGE = 0.75


def trillium_deductible(net_income: float) -> int:
    return int(round(max(net_income - TRILLIUM_BASE_DEDUCTION, 0) * TRILLIUM_RATE + TRILLIUM_FLAT))


def cdb_estimated_amount(profile) -> int:
    partnered = profile.marital_status.value in ("married", "common_law")
    threshold = CDB_THRESHOLD_PARTNERED if partnered else CDB_THRESHOLD_SINGLE
    reduction = max(profile.adjusted_family_net_income() - threshold, 0) * CDB_REDUCTION_RATE
    return int(round(max(CDB_MAX_ANNUAL - reduction, 0)))


@dataclass
class Program:
    id: str
    name: str
    jurisdiction: str
    evaluate: Callable[[Profile], ProgramResult]


def _r(**kw) -> ProgramResult:
    return ProgramResult(**kw)


def eval_dtc(p: Profile) -> ProgramResult:
    if p.has_dtc_certificate:
        return _r(program_id="dtc", program_name="Disability Tax Credit", jurisdiction="Federal (CRA)",
                  eligibility=Eligibility.eligible, confidence=0.99, estimated_annual_value=DTC_FEDERAL_VALUE,
                  value_is_illustrative=False,
                  reasons=["You already hold a valid DTC certificate."],
                  next_steps=["Make sure the DTC is claimed on your tax return each year."])
    if p.has_severe_prolonged_impairment:
        return _r(program_id="dtc", program_name="Disability Tax Credit", jurisdiction="Federal (CRA)",
                  eligibility=Eligibility.maybe, confidence=0.6, estimated_annual_value=DTC_FEDERAL_VALUE,
                  value_is_illustrative=False,
                  reasons=["You reported a severe and prolonged impairment, which may qualify for the DTC.",
                           "The DTC is a KEY that can unlock several other programs."],
                  next_steps=["Complete Form T2201 Part A.",
                              "Have your medical practitioner complete Part B.",
                              "Submit Form T2201 to the CRA (online or by mail)."])
    return _r(program_id="dtc", program_name="Disability Tax Credit", jurisdiction="Federal (CRA)",
              eligibility=Eligibility.not_eligible, confidence=0.8, estimated_annual_value=None,
              reasons=["No severe and prolonged impairment reported."], next_steps=[])


def eval_cdb(p: Profile) -> ProgramResult:
    dtc = p.has_dtc_certificate or p.has_severe_prolonged_impairment
    if dtc and 18 <= p.age <= 64:
        return _r(program_id="cdb", program_name="Canada Disability Benefit", jurisdiction="Federal (ESDC)",
                  eligibility=Eligibility.likely if p.has_dtc_certificate else Eligibility.maybe, confidence=0.7,
                  estimated_annual_value=cdb_estimated_amount(p), value_is_illustrative=False,
                  reasons=[f"For low-income people aged 18–64 with a valid DTC (up to ${CDB_MAX_ANNUAL:,}/yr)."],
                  next_steps=["Apply once your DTC is approved; file taxes to establish income."])
    reasons = []
    if not dtc:
        reasons.append("Requires a DTC certificate.")
    if p.age > 64:
        reasons.append("For ages 18–64; at 65+ the OAS/GIS stream applies instead.")
    elif p.age < 18:
        reasons.append("For ages 18–64.")
    return _r(program_id="cdb", program_name="Canada Disability Benefit", jurisdiction="Federal (ESDC)",
              eligibility=Eligibility.not_eligible, confidence=0.8, estimated_annual_value=None,
              reasons=reasons, next_steps=[])


def eval_cdcp(p: Profile) -> ProgramResult:
    reasons: list[str] = []
    ok = True
    if p.has_private_dental_insurance:
        ok = False
        reasons.append("You have private/workplace dental insurance, which usually makes you ineligible.")
    afni = p.adjusted_family_net_income()
    if afni >= CDCP_INCOME_CAP:
        ok = False
        reasons.append(f"Adjusted family net income (${afni:,.0f}) is at or above the ${CDCP_INCOME_CAP:,.0f} cap.")
    if not p.filed_taxes_last_year:
        ok = False
        reasons.append("You (and a spouse, if any) must have filed last year's tax return.")
    if not p.canadian_resident:
        ok = False
        reasons.append("Must be a Canadian resident.")
    if ok:
        pct = cdcp_coverage_pct(afni)
        reasons.insert(0, "Open to anyone without dental insurance and with adjusted family net income "
                          f"under ${CDCP_INCOME_CAP:,.0f} (all ages, since the May 2025 expansion).")
        reasons.append(f"At your income the plan pays {pct}% of the set fee for eligible dental care. "
                       "The cash value depends on the treatment you need, so there is no fixed yearly amount.")
        return _r(program_id="cdcp", program_name="Canadian Dental Care Plan", jurisdiction="Federal (Health Canada)",
                  eligibility=Eligibility.eligible, confidence=0.9, estimated_annual_value=None,
                  reasons=reasons,
                  next_steps=["Apply at canada.ca/dental or call 1-833-537-4342.",
                              "Renew coverage every year by the annual deadline."])
    return _r(program_id="cdcp", program_name="Canadian Dental Care Plan", jurisdiction="Federal (Health Canada)",
              eligibility=Eligibility.not_eligible, confidence=0.8, estimated_annual_value=None,
              reasons=reasons, next_steps=[])


def eval_metc(p: Profile) -> ProgramResult:
    threshold = min(0.03 * p.annual_net_income, METC_FIXED_THRESHOLD)
    excess = p.out_of_pocket_medical_annual - threshold
    if excess > 0:
        value = round(METC_FEDERAL_RATE * excess)
        return _r(program_id="metc", program_name="Medical Expense Tax Credit", jurisdiction="Federal (CRA)",
                  eligibility=Eligibility.eligible, confidence=0.85, estimated_annual_value=value,
                  value_is_illustrative=False,
                  reasons=[f"Out-of-pocket medical costs (${p.out_of_pocket_medical_annual:,.0f}) exceed the "
                           f"${threshold:,.0f} threshold (lesser of 3% of net income or ${METC_FIXED_THRESHOLD:,}).",
                           f"Claimable portion ≈ ${excess:,.0f} at the {int(METC_FEDERAL_RATE*100)}% federal rate."],
                  next_steps=["Keep all medical receipts (CRA requires 6 years).",
                              "Claim on line 33099 of your return."])
    return _r(program_id="metc", program_name="Medical Expense Tax Credit", jurisdiction="Federal (CRA)",
              eligibility=Eligibility.not_eligible, confidence=0.7, estimated_annual_value=None,
              reasons=[f"Medical costs did not exceed the ${threshold:,.0f} threshold."], next_steps=[])


def eval_caregiver(p: Profile) -> ProgramResult:
    if p.is_caregiver:
        return _r(program_id="ccc", program_name="Canada Caregiver Credit", jurisdiction="Federal (CRA)",
                  eligibility=Eligibility.maybe, confidence=0.7, estimated_annual_value=None,
                  reasons=["You reported supporting a dependant with a physical or mental impairment."],
                  next_steps=["Confirm the dependant's net income and relationship.",
                              "Claim on the applicable line (30450/30500) of your return."])
    return _r(program_id="ccc", program_name="Canada Caregiver Credit", jurisdiction="Federal (CRA)",
              eligibility=Eligibility.not_eligible, confidence=0.8, estimated_annual_value=None,
              reasons=["You did not report caregiving for a dependant with an impairment."], next_steps=[])


def eval_rdsp(p: Profile) -> ProgramResult:
    dtc = p.has_dtc_certificate or p.has_severe_prolonged_impairment
    if dtc and p.age < 60:
        return _r(program_id="rdsp", program_name="Registered Disability Savings Plan", jurisdiction="Federal (ESDC)",
                  eligibility=Eligibility.likely if p.has_dtc_certificate else Eligibility.maybe, confidence=0.7,
                  estimated_annual_value=None,
                  reasons=["Requires DTC eligibility; attracts matching government grants and bonds."],
                  next_steps=["Open an RDSP at a participating financial institution once DTC is approved."])
    reasons = []
    if not dtc:
        reasons.append("Requires a DTC certificate (or DTC-eligible impairment).")
    if p.age >= 60:
        reasons.append("An RDSP must be opened before age 60.")
    return _r(program_id="rdsp", program_name="Registered Disability Savings Plan", jurisdiction="Federal (ESDC)",
              eligibility=Eligibility.not_eligible, confidence=0.8, estimated_annual_value=None,
              reasons=reasons, next_steps=[])


def eval_trillium(p: Profile) -> ProgramResult:
    if p.province != "ON":
        return _r(program_id="otdp", program_name="Ontario Trillium Drug Program", jurisdiction="Ontario",
                  eligibility=Eligibility.not_eligible, confidence=0.9, estimated_annual_value=None,
                  reasons=["Only available to Ontario residents."], next_steps=[])
    if p.age >= ODB_MIN_AGE:
        return _r(program_id="otdp", program_name="Ontario Trillium Drug Program", jurisdiction="Ontario",
                  eligibility=Eligibility.not_eligible, confidence=0.8, estimated_annual_value=None,
                  reasons=[f"At {ODB_MIN_AGE}+ the Ontario Drug Benefit covers your prescriptions instead."],
                  next_steps=[])
    if p.age < OHIP_PLUS_MAX_AGE:
        return _r(program_id="otdp", program_name="Ontario Trillium Drug Program", jurisdiction="Ontario",
                  eligibility=Eligibility.not_eligible, confidence=0.8, estimated_annual_value=None,
                  reasons=[f"Under {OHIP_PLUS_MAX_AGE}, OHIP+ covers your prescriptions instead."],
                  next_steps=[])
    if p.prescription_costs_annual <= 0:
        return _r(program_id="otdp", program_name="Ontario Trillium Drug Program", jurisdiction="Ontario",
                  eligibility=Eligibility.not_eligible, confidence=0.6, estimated_annual_value=None,
                  reasons=["No prescription drug costs reported."], next_steps=[])
    deductible = trillium_deductible(p.annual_net_income)
    if p.prescription_costs_annual > deductible:
        covered = round(p.prescription_costs_annual - deductible)
        return _r(program_id="otdp", program_name="Ontario Trillium Drug Program", jurisdiction="Ontario",
                  eligibility=Eligibility.eligible, confidence=0.75, estimated_annual_value=covered,
                  value_is_illustrative=False,
                  reasons=[f"Prescription costs (${p.prescription_costs_annual:,.0f}) exceed your estimated "
                           f"income-tested deductible (${deductible:,.0f}); Trillium covers most costs above it."],
                  next_steps=["Apply through the Ontario Trillium Drug Program (form + your pharmacy)."])
    return _r(program_id="otdp", program_name="Ontario Trillium Drug Program", jurisdiction="Ontario",
              eligibility=Eligibility.maybe, confidence=0.5, estimated_annual_value=None,
              reasons=[f"Prescription costs may not exceed your estimated deductible (${deductible:,.0f})."],
              next_steps=["Still worth applying if your drug costs are high relative to income."])


def eval_odb(p: Profile) -> ProgramResult:
    if p.province == "ON" and p.canadian_resident and p.age >= ODB_MIN_AGE:
        val = round(p.prescription_costs_annual * 0.9) if p.prescription_costs_annual > 0 else None
        return _r(program_id="odb", program_name="Ontario Drug Benefit", jurisdiction="Ontario",
                  eligibility=Eligibility.eligible, confidence=0.95, estimated_annual_value=val,
                  reasons=[f"At {ODB_MIN_AGE}+ in Ontario you are automatically covered for most "
                           "prescription drugs under the ODB (small co-pay)."],
                  next_steps=["Automatic at 65; show your Ontario health card at the pharmacy."])
    reasons = ["Ontario Drug Benefit is for Ontario residents."] if p.province != "ON" \
        else [f"Automatic at age {ODB_MIN_AGE}; under 65, see OHIP+ or Trillium instead."]
    return _r(program_id="odb", program_name="Ontario Drug Benefit", jurisdiction="Ontario",
              eligibility=Eligibility.not_eligible, confidence=0.85, estimated_annual_value=None,
              reasons=reasons, next_steps=[])


def eval_ohip_plus(p: Profile) -> ProgramResult:
    if p.province == "ON" and p.canadian_resident and p.age < OHIP_PLUS_MAX_AGE:
        val = round(p.prescription_costs_annual) if p.prescription_costs_annual > 0 else None
        return _r(program_id="ohipplus", program_name="OHIP+", jurisdiction="Ontario",
                  eligibility=Eligibility.eligible, confidence=0.85, estimated_annual_value=val,
                  reasons=[f"Under {OHIP_PLUS_MAX_AGE} in Ontario, prescription drugs are free under "
                           "OHIP+ for anyone without a private drug plan."],
                  next_steps=["Show your health card at the pharmacy; no enrolment needed without a private plan."])
    reasons = ["OHIP+ is for Ontario residents."] if p.province != "ON" \
        else [f"OHIP+ covers Ontarians under {OHIP_PLUS_MAX_AGE}."]
    return _r(program_id="ohipplus", program_name="OHIP+", jurisdiction="Ontario",
              eligibility=Eligibility.not_eligible, confidence=0.85, estimated_annual_value=None,
              reasons=reasons, next_steps=[])


def eval_adp(p: Profile) -> ProgramResult:
    if p.province == "ON" and p.canadian_resident and p.has_severe_prolonged_impairment:
        return _r(program_id="adp", program_name="Assistive Devices Program", jurisdiction="Ontario",
                  eligibility=Eligibility.maybe, confidence=0.6, estimated_annual_value=None,
                  value_is_illustrative=True,
                  reasons=[f"A long-term physical disability can qualify you for the ADP, which funds "
                           f"about {int(ADP_COVERAGE*100)}% of approved equipment (mobility, hearing, "
                           "respiratory and more)."],
                  next_steps=["A registered health professional authorizes the equipment before purchase.",
                              "Buy from an ADP-authorized vendor."])
    reasons = ["The Assistive Devices Program is for Ontario residents."] if p.province != "ON" \
        else ["ADP funds equipment for a long-term physical disability; none was reported."]
    return _r(program_id="adp", program_name="Assistive Devices Program", jurisdiction="Ontario",
              eligibility=Eligibility.not_eligible, confidence=0.7, estimated_annual_value=None,
              reasons=reasons, next_steps=[])


# Date the figures above were last checked against official sources, and the official page per
# program. Surfaced in the UI so the numbers are traceable, not just asserted.
RATES_VERIFIED = "2026-10-21"
SOURCES: dict[str, str] = {
    "dtc": "https://www.canada.ca/en/revenue-agency/services/tax/individuals/segments/tax-credits-deductions-persons-disabilities/disability-tax-credit.html",
    "cdb": "https://www.canada.ca/en/services/benefits/disability/canada-disability-benefit/amount.html",
    "cdcp": "https://www.canada.ca/en/services/benefits/dental/dental-care-plan/qualify.html",
    "metc": "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/deductions-credits-expenses/lines-33099-33199-eligible-medical-expenses-you-claim-on-your-tax-return.html",
    "ccc": "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/deductions-credits-expenses/line-30450-canada-caregiver-amount-other-infirm-dependants-age-18-older-including-parent-grandparent.html",
    "rdsp": "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/registered-disability-savings-plan-rdsp.html",
    "otdp": "https://www.ontario.ca/page/get-help-high-prescription-drug-costs",
    "odb": "https://www.ontario.ca/page/get-help-high-prescription-drug-costs",
    "ohipplus": "https://www.ontario.ca/page/learn-about-ohip-plus",
    "adp": "https://www.ontario.ca/page/assistive-devices-program",
}


PROGRAMS: list[Program] = [
    Program("dtc", "Disability Tax Credit", "Federal (CRA)", eval_dtc),
    Program("cdb", "Canada Disability Benefit", "Federal (ESDC)", eval_cdb),
    Program("cdcp", "Canadian Dental Care Plan", "Federal (Health Canada)", eval_cdcp),
    Program("metc", "Medical Expense Tax Credit", "Federal (CRA)", eval_metc),
    Program("ccc", "Canada Caregiver Credit", "Federal (CRA)", eval_caregiver),
    Program("rdsp", "Registered Disability Savings Plan", "Federal (ESDC)", eval_rdsp),
    Program("otdp", "Ontario Trillium Drug Program", "Ontario", eval_trillium),
    Program("odb", "Ontario Drug Benefit", "Ontario", eval_odb),
    Program("ohipplus", "OHIP+", "Ontario", eval_ohip_plus),
    Program("adp", "Assistive Devices Program", "Ontario", eval_adp),
]
