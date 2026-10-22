"""Home-care journey: Direct Funding (CILT) screening + application preparation.

A focused, single-path slice: screen against the real DF criteria, estimate the real monthly
budget, and lay out the real application the person completes in their own words. Covered prepares
and tracks; the DF interview panel at CILT decides, and the applicant owns the form.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain import direct_funding as df
from app.domain import ontario_health_athome as oha

router = APIRouter(prefix="/homecare", tags=["homecare"])


class DFScreenIn(BaseModel):
    age: int = 0
    ontario_resident: bool = True
    has_ohip: bool = True
    permanent_physical_disability: bool = False
    tasks: list[str] = []
    needs_stable_1yr: bool = False
    can_self_manage: bool = False
    hours_per_week: float = 0.0


def _application_outline(eligible: bool) -> list[dict]:
    """The real DF application sections, with who completes each and what Covered can prepare.
    CILT requires the applicant to complete the form in their own words; others may help physically
    but may not lead. So Covered drafts and organizes; the applicant confirms and signs."""
    if not eligible:
        return []
    return [
        {"section": "Applicant & alternate contact", "who": "you",
         "note": "Your details, plus an alternate contact CILT can reach (not someone to speak for you)."},
        {"section": "Your disability & attendant-service needs", "who": "you",
         "note": "Questions 1-6, including essential communication. In your own words; Covered drafts a starting point."},
        {"section": "Insurance disclosure", "who": "you",
         "note": "Question 10: any insurance, settlement or WSIB payments. DF is the last payer."},
        {"section": "Attendant Service Log", "who": "you",
         "note": "Question 11: a week of your current help, logged over 24-hour days, then x4.33 for a month."},
        {"section": "Proposed Service Plan", "who": "covered-assisted",
         "note": "Question 12: the hours you need. Covered totals this from your weekly hours."},
        {"section": "Monthly Budget Calculation", "who": "covered-assisted",
         "note": "Question 13: wages at $22/hr, 21% MERCs, admin and 5% contingency. Covered calculates it."},
        {"section": "Self-assessment (optional)", "who": "you",
         "note": "Question 14: show your self-management experience. Optional but strengthens the application."},
        {"section": "Sign & send to CILT", "who": "you",
         "note": "Sign the application and send a copy to CILT; keep your own. It joins the waiting list."},
    ]


@router.post("/screen")
async def homecare_screen(body: DFScreenIn) -> dict:
    """The home-care fork: self-managed Direct Funding vs agency-arranged Ontario Health atHome.

    Direct Funding needs you to direct your own attendants; atHome arranges care for you. We present
    both and recommend the one that fits your self-management answer, since the choice is yours.
    """
    r = df.screen(**body.model_dump())
    eligible = r.eligibility in ("likely", "maybe")
    direct_funding = {
        "program": "direct_funding",
        "name": "Direct Funding",
        "subtitle": "Self-managed attendant services",
        "administered_by": "Centre for Independent Living in Toronto (CILT)",
        "eligibility": r.eligibility,
        "reasons": r.reasons,
        "next_steps": r.next_steps,
        "monthly_budget": r.monthly_budget,
        "monthly_hours": r.monthly_hours,
        "budget_breakdown": r.budget_breakdown,
        "application": _application_outline(eligible),
        "source_url": df.SOURCE_URL,
        "guide_url": df.GUIDE_URL,
        "rates_verified": df.VERIFIED,
        "cilt_phone": df.CILT_PHONE,
        "cilt_email": df.CILT_EMAIL,
        "disclaimer": ("Estimates and eligibility are a guide only. The DF eligibility interview panel "
                       "at CILT makes the final decision, and there is a province-wide waiting list."),
    }
    athome = oha.route(ontario_resident=body.ontario_resident, has_ohip=body.has_ohip)

    # Recommend DF when the person can self-manage and qualifies; otherwise agency-arranged atHome.
    if r.eligibility == "likely":
        recommended = "direct_funding"
    elif athome["fit"]:
        recommended = "athome"
    else:
        recommended = "direct_funding"  # neither is a clean fit; DF carries the specific reasons why
    return {"recommended": recommended, "direct_funding": direct_funding, "athome": athome}


@router.get("/tasks")
async def homecare_tasks() -> dict:
    """The eight attendant-service activities (the first four are hands-on personal care)."""
    return {"tasks": [{"id": t, "label": label, "core": t in df.CORE_TASKS} for t, label in df.TASKS]}
