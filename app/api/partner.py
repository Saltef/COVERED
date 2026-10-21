"""Partner embed API (v1).

The benefits engine, exposed for other systems to call directly. A pharmacy portal,
tax-filing app, bank, or caseworker tool POSTs a profile and gets back the programs the
person is likely owed, with dollar values and next steps. Authenticated with a partner key
(X-Covered-Key), not a Clerk user, because the caller is a system, not an end user.

The response is a stable, versioned contract. Screening is the same pure function the
in-house app uses, so accuracy matches what /benchmark verifies. No LLM call on the hot
path, so the endpoint is fast and deterministic.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.schemas import ProfileIn
from app.config import Settings, get_settings
from app.domain.rules_engine import screen, summarize

router = APIRouter(prefix="/v1", tags=["partner"])

API_VERSION = "1.0"
DEMO_KEY = "demo-partner-key"  # dev only: always accepted when auth fallback is on
DISCLAIMER = (
    "Estimates use 2025-2026 CRA and Ontario rates and depend on the person's situation. "
    "Covered prepares applications; it never files on anyone's behalf."
)


async def require_partner_key(
    x_covered_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """Accept a configured partner key; in dev also accept the built-in demo key."""
    keys = set(settings.partner_key_set)
    if settings.dev_allow_no_auth and not settings.is_production:
        keys.add(DEMO_KEY)
    if not keys:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No partner keys configured")
    if not x_covered_key or x_covered_key not in keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-Covered-Key")
    return x_covered_key


@router.post("/eligibility")
async def eligibility(
    profile_in: ProfileIn,
    _key: str = Depends(require_partner_key),
) -> dict:
    """Screen a profile and return the programs it is likely owed (stable v1 contract)."""
    results = screen(profile_in.to_domain())
    s = summarize(results)
    order = {"eligible": 0, "likely": 1, "maybe": 2, "not_eligible": 3}
    programs = [
        {
            "id": r.program_id,
            "name": r.program_name,
            "jurisdiction": r.jurisdiction,
            "eligibility": r.eligibility.value,
            "confidence": r.confidence,
            "estimated_annual_value": r.estimated_annual_value,
            "value_is_illustrative": r.value_is_illustrative,
            "reasons": r.reasons,
            "next_steps": r.next_steps,
            "unlocked_by": r.unlocked_by,
        }
        for r in results
    ]
    programs.sort(key=lambda p: (order.get(p["eligibility"], 9), -(p["estimated_annual_value"] or 0)))
    return {
        "api_version": API_VERSION,
        "currency": "CAD",
        "total_estimated_annual": s["total_estimated_annual"],
        "programs_claimable": s["n_eligible_or_maybe"],
        "programs": programs,
        "disclaimer": DISCLAIMER,
    }
