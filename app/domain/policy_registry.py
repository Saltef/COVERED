"""Policy rule registry: the single checkable record of each eligibility figure.

This is the link between the deterministic engine and the AI policy checker. Each entry is a
parameter the engine encodes, with the official source and the exact value. A test locks the
engine's constants to these values (so they cannot silently diverge), and the AI drift checker
(app/ops/policy_checker.py) re-reads each source and flags when the live page disagrees.

`checkable=False` marks figures whose source is a PDF or a formula that cannot be auto-extracted
reliably; those stay manual-review.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Rule:
    id: str
    program: str
    label: str          # plain description of the parameter
    value: float        # the engine's current value (and what the checker compares against)
    display: str        # how it reads, e.g. "$90,000"
    source_url: str
    query: str          # what the checker searches/extracts on the page
    verified_date: str
    checkable: bool = True   # False for PDF / formula sources (manual review)
    note: str = ""


_CANADA = "https://www.canada.ca/en"
REGISTRY: list[Rule] = [
    Rule(
        id="cdcp_income_cap", program="cdcp",
        label="Canadian Dental Care Plan: adjusted family net income cap",
        value=90_000, display="$90,000",
        source_url=f"{_CANADA}/services/benefits/dental/dental-care-plan/qualify.html",
        query="adjusted family net income threshold to qualify for the Canadian Dental Care Plan",
        verified_date="2026-10-21"),
    Rule(
        id="metc_threshold", program="metc",
        label="Medical Expense Tax Credit: fixed threshold (lesser of 3% of net income or this amount)",
        value=2_834, display="$2,834",
        source_url=f"{_CANADA}/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/deductions-credits-expenses/lines-33099-33199-eligible-medical-expenses-you-claim-on-your-tax-return.html",
        query="the fixed dollar amount in the lesser of 3% of net income or this amount, medical expenses 2025",
        verified_date="2026-10-21"),
    Rule(
        id="cdb_max_annual", program="cdb",
        label="Canada Disability Benefit: maximum amount per year",
        value=2_450, display="$2,450/yr",
        source_url=f"{_CANADA}/services/benefits/disability/canada-disability-benefit/amount.html",
        query="maximum Canada Disability Benefit amount per year or per month",
        verified_date="2026-10-21",
        note="Engine uses the Jul 2026-Jun 2027 indexed figure; canada.ca pages differ on the forward "
             "amount, so a mismatch here may be legitimate drift to review."),
    Rule(
        id="cdb_threshold_single", program="cdb",
        label="Canada Disability Benefit: single-beneficiary income threshold before reduction",
        value=23_483, display="$23,483",
        source_url=f"{_CANADA}/services/benefits/disability/canada-disability-benefit/amount.html",
        query="single person adjusted family net income threshold where the Canada Disability Benefit starts to reduce",
        verified_date="2026-10-21",
        note="2026-27 indexed; see cdb_max_annual note."),
    Rule(
        id="dtc_disability_amount", program="dtc",
        label="Disability Tax Credit: federal base disability amount",
        value=10_138, display="$10,138",
        source_url=f"{_CANADA}/revenue-agency/services/tax/individuals/segments/tax-credits-deductions-persons-disabilities/disability-tax-credit.html",
        query="federal disability amount base for the Disability Tax Credit",
        verified_date="2026-10-21"),

    # Manual-review figures (PDF guide or a formula; not auto-extractable reliably).
    Rule(id="metc_federal_rate", program="metc", label="Medical Expense Tax Credit: federal rate",
         value=0.15, display="15%",
         source_url=f"{_CANADA}/revenue-agency/services/tax/individuals/frequently-asked-questions-individuals/canadian-income-tax-rates-individuals-current-previous-years.html",
         query="", verified_date="2026-10-21", checkable=False, note="Lowest federal personal rate; formula."),
    Rule(id="df_wage", program="direct_funding", label="Direct Funding: max average attendant wage",
         value=22.00, display="$22.00/hr",
         source_url="https://www.dfontario.ca/df_public/df_application_guide_may2023_2_en.pdf",
         query="", verified_date="2026-10-22", checkable=False, note="CILT PDF guide; manual."),
    Rule(id="df_max_hours_month", program="direct_funding", label="Direct Funding: max attendant hours/month",
         value=212.2, display="212.2 hrs/mo",
         source_url="https://www.dfontario.ca/df_public/df_application_guide_may2023_2_en.pdf",
         query="", verified_date="2026-10-22", checkable=False, note="CILT PDF guide; manual."),
]
