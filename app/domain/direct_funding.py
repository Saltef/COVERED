"""Direct Funding (DF): Ontario's self-managed attendant services.

Funded by the Ontario Ministry of Health, administered by the Centre for Independent Living in
Toronto (CILT). A person with a permanent physical disability becomes the employer of their own
attendants and receives a monthly budget to hire, train, schedule and direct them.

Rules and figures are from the DF Application Guide (May 2023, 8th edition) and Ontario
Regulation 367/94. Deterministic and auditable, like the rest of app/domain (stdlib only).
The eligibility interview panel makes the final determination, so this screens to "likely" at best.

Source: https://www.dfontario.ca
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE_URL = "https://www.dfontario.ca"
GUIDE_URL = "https://www.dfontario.ca/df_public/df_application_guide_may2023_2_en.pdf"
VERIFIED = "2026-10-22"
CILT_PHONE = "1-800-354-9950"
CILT_EMAIL = "dfinfo@cilt.ca"

MIN_AGE = 16
MAX_HOURS_MONTH = 212.2        # an average of 7 hours/day
WAGE = 22.00                   # maximum allowable average hourly wage
MERC_RATE = 0.21               # employer MERCs (CPP, EI, vacation, holiday, WSIB)
MISC_MONTHLY = 215             # bookkeeper 170 + advertising 25 + bank 10 + liability 10
CONTINGENCY_RATE = 0.05        # retained by CILT, accessed if needed

# The eight attendant-service activities (Reg 367/94, clause (c)). At least TWO are required, and
# at least one from the first FOUR (hands-on personal care).
TASKS = [
    ("transfer", "Turning in bed, lifting, positioning or transferring"),
    ("bathing", "Washing, bathing, showering, shaving or grooming"),
    ("dressing", "Dressing or undressing"),
    ("toileting", "Catheter, leg bag, toilet, urination or bowel routines"),
    ("breathing", "Breathing, tracheotomy or respiratory equipment"),
    ("eating", "Eating"),
    ("household", "Meal preparation, dishwashing, laundry or housekeeping"),
    ("communication", "Assistance with essential communication"),
]
CORE_TASKS = {"transfer", "bathing", "dressing", "toileting"}  # the hands-on first four


@dataclass
class DFResult:
    eligibility: str          # "likely" | "maybe" | "not_eligible"
    reasons: list[str]
    next_steps: list[str]
    monthly_budget: float | None = None
    monthly_hours: float | None = None
    budget_breakdown: dict | None = None


def estimate_budget(hours_per_week: float) -> dict:
    """The DF monthly budget, using the guide's own formula and rates."""
    monthly_hours = min(round(max(hours_per_week, 0) * 4.33, 1), MAX_HOURS_MONTH)
    wages = monthly_hours * WAGE
    mercs = wages * MERC_RATE
    subtotal = wages + mercs + MISC_MONTHLY
    contingency = subtotal * CONTINGENCY_RATE
    total = subtotal + contingency
    return {
        "monthly_hours": monthly_hours,
        "wages": round(wages),
        "mercs": round(mercs),
        "misc": MISC_MONTHLY,
        "contingency": round(contingency),
        "monthly_total": round(total),
        "annual_total": round(total * 12),
        "capped": monthly_hours >= MAX_HOURS_MONTH,
    }


def screen(*, age: int = 0, ontario_resident: bool = True, has_ohip: bool = True,
           permanent_physical_disability: bool = False, tasks: list[str] | None = None,
           needs_stable_1yr: bool = False, can_self_manage: bool = False,
           hours_per_week: float = 0.0) -> DFResult:
    """Screen one person against the DF eligibility criteria. Final say is the interview panel."""
    blockers: list[str] = []
    if not ontario_resident:
        blockers.append("Direct Funding is for Ontario residents.")
    if not has_ohip:
        blockers.append("A valid Ontario Health Card is required.")
    if age < MIN_AGE:
        blockers.append(f"You must be at least {MIN_AGE} years old.")
    if not permanent_physical_disability:
        blockers.append("DF funds attendant services needed because of a permanent physical disability.")
    task_set = set(tasks or [])
    if not (len(task_set) >= 2 and task_set & CORE_TASKS):
        blockers.append("DF needs attendant help with at least two daily activities, including at "
                        "least one hands-on personal-care task (transfers, bathing, dressing or toileting).")
    if not needs_stable_1yr:
        blockers.append("Your attendant-service needs must have been stable for at least a year.")

    if blockers:
        return DFResult("not_eligible", blockers,
                        [f"Check who qualifies at dfontario.ca, or ask CILT at {CILT_PHONE}.",
                         "Agency-delivered home care through Ontario Health atHome may fit instead."])

    reasons = [
        "You meet the care-need criteria: a permanent physical disability needing hands-on attendant "
        "services, stable for at least a year.",
        "Direct Funding lets you hire, schedule and direct your own attendants with a monthly budget.",
    ]
    if can_self_manage:
        eligibility = "likely"
        reasons.append("You indicated you can self-manage attendants (recruiting, scheduling, training "
                       "and the employer responsibilities), which DF requires.")
    else:
        eligibility = "maybe"
        reasons.append("DF requires that you direct your own attendants. If you are unsure you can "
                       "self-manage, the eligibility interview is where that is assessed, and CILT can "
                       "help you prepare.")

    next_steps = [
        "Complete the Direct Funding application in your own words (CILT allows physical help filling it in).",
        "Sign it and send a copy to CILT; it joins the province-wide waiting list.",
        "At the top of the list, CILT prepares you for an eligibility interview, held with you alone.",
        f"Questions: CILT Direct Funding at {CILT_PHONE} or {CILT_EMAIL}.",
    ]

    result = DFResult(eligibility, reasons, next_steps)
    if hours_per_week:
        b = estimate_budget(hours_per_week)
        result.monthly_budget = b["monthly_total"]
        result.monthly_hours = b["monthly_hours"]
        result.budget_breakdown = b
    return result
