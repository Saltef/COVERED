"""Care-team, clinician, and attestation endpoints (patient-centric)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import care_team_repo as ct
from app.db import repository as repo
from app.domain.applications import build_partb_context
from app.security.auth import Principal, Role, get_current_user
from app.security.authz import require_role

router = APIRouter()


# ----- patient: manage the care team -----
class InviteIn(BaseModel):
    email: str
    role: str = "clinician"
    scope: list[str] = ["read"]


@router.post("/me/care-team/invite")
async def invite(body: InviteIn, user: Principal = Depends(get_current_user)) -> dict:
    try:
        grant = await ct.invite_member(user.user_id, body.email, body.role, body.scope)
        await repo.write_audit(user.user_id, "invite_member", body.email)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    return grant


@router.get("/me/care-team")
async def my_care_team(user: Principal = Depends(get_current_user)) -> list[dict]:
    try:
        return await ct.list_care_team(user.user_id)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")


@router.post("/me/care-team/{grant_id}/revoke")
async def revoke(grant_id: str, user: Principal = Depends(get_current_user)) -> dict:
    try:
        await ct.revoke_grant(user.user_id, grant_id)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    return {"ok": True}


# ----- clinician: verify + queue + attest -----
class VerifyIn(BaseModel):
    full_name: str
    license_number: str
    college: str = ""
    province: str = ""


@router.post("/clinician/verify")
async def clinician_verify(body: VerifyIn, user: Principal = Depends(require_role(Role.clinician))) -> dict:
    try:
        return await ct.verify_clinician(user.user_id, body.full_name, body.license_number,
                                         body.college, body.province)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")


@router.get("/clinician/me")
async def clinician_me(user: Principal = Depends(require_role(Role.clinician))) -> dict:
    try:
        prof = await ct.get_clinician_profile(user.user_id)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    return prof or {"status": "unverified"}


@router.get("/clinician/pending")
async def clinician_pending(user: Principal = Depends(require_role(Role.clinician))) -> dict:
    try:
        verified = await ct.is_verified_clinician(user.user_id)
        pending = await ct.list_clinician_pending(user.user_id)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    for item in pending:
        item["partb"] = build_partb_context(item.get("profile") or {})
        item.pop("profile", None)  # minimum necessary: don't ship the full financial profile
    return {"verified": verified, "pending": pending}


class AttestIn(BaseModel):
    screening_id: str
    cra_reference_number: str = ""
    fields: dict = {}


@router.post("/attestations")
async def attest(body: AttestIn, user: Principal = Depends(require_role(Role.clinician))) -> dict:
    try:
        if not await ct.is_verified_clinician(user.user_id):
            raise HTTPException(403, "clinician is not verified")
        res = await ct.create_attestation(user.user_id, body.screening_id, body.fields, body.cra_reference_number)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    if res is None:
        raise HTTPException(404, "screening not found")
    if res.get("error"):
        raise HTTPException(403, res["error"])
    return res


@router.post("/attestations/{att_id}/mark-submitted")
async def mark_submitted(att_id: str, user: Principal = Depends(require_role(Role.clinician))) -> dict:
    try:
        await ct.mark_attestation_submitted(user.user_id, att_id)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    return {"ok": True}
