"""Per-user persistence endpoints. Every record is row-level-scoped to the caller."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.schemas import ProfileIn, ProgramResultOut
from app.db import care_team_repo as ct
from app.db import repository as repo
from app.domain.rules_engine import screen, summarize
from app.security.auth import Principal, Role, get_current_user
from app.security.authz import require_role

router = APIRouter()


def _headline(s: dict) -> str:
    return (f"You could be owed about ${s['total_estimated_annual']:,.0f} a year across "
            f"{s['n_eligible_or_maybe']} programs you may not be getting.")


@router.post("/me/screenings")
async def save_my_screening(
    profile_in: ProfileIn,
    user: Principal = Depends(require_role(Role.senior, Role.caregiver, Role.support_worker)),
) -> dict:
    results = screen(profile_in.to_domain())
    s = summarize(results)
    headline = _headline(s)
    out = [ProgramResultOut.from_domain(r).model_dump(mode="json") for r in results]
    try:
        saved = await repo.save_screening(user.user_id, headline, profile_in.model_dump(mode="json"), out, s)
        await repo.write_audit(user.user_id, "screen", user.user_id,
                               f"Screened {profile_in.first_name or 'a client'}")
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    return {"id": saved.get("id"), "headline": headline, "summary": s}


@router.post("/extract")
async def extract_document(
    file: UploadFile = File(...),
    user: Principal = Depends(get_current_user),
) -> dict:
    """Read a document (e.g. a Notice of Assessment) and return profile fields to pre-fill."""
    from app.agents.extract import extract_profile_fields
    data = await file.read()
    return await extract_profile_fields(data, file.content_type or "image/png")


@router.get("/me/screenings")
async def list_my_screenings(user: Principal = Depends(get_current_user)) -> list[dict]:
    try:
        return await repo.list_screenings(user)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")


@router.get("/me/screenings/{rid}")
async def get_my_screening(rid: str, user: Principal = Depends(get_current_user)) -> dict:
    try:
        rec = await repo.get_screening(user, rid)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    if rec is None:
        raise HTTPException(404, "not found")
    return rec


class StatusIn(BaseModel):
    status: str


@router.get("/me/screenings/{rid}/status")
async def screening_status(rid: str, user: Principal = Depends(get_current_user)) -> dict:
    try:
        rec = await repo.get_screening(user, rid)
        if rec is None:
            raise HTTPException(404, "not found")
        statuses = await repo.get_program_statuses(rid)
        att = await ct.get_attestation_for_screening(rid)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    if att:  # the DTC status is driven by the clinician's Part B attestation
        statuses["dtc"] = "submitted_to_cra" if att.get("status") == "submitted_in_cra" else "partb_attested"
    return {"statuses": statuses, "attestation": att}


@router.post("/me/screenings/{rid}/status/{program_id}")
async def set_screening_status(
    rid: str, program_id: str, body: StatusIn,
    user: Principal = Depends(require_role(Role.senior, Role.caregiver, Role.support_worker)),
) -> dict:
    try:
        rec = await repo.get_screening(user, rid)
        if rec is None:
            raise HTTPException(404, "not found")
        await repo.set_program_status(rec.get("owner"), rid, program_id, body.status)
        await repo.write_audit(user.user_id, "status", rec.get("owner"),
                               f"Marked {program_id.upper()} {body.status}")
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    return {"ok": True}
