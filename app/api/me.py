"""Per-user persistence endpoints. Every record is row-level-scoped to the caller."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import ProfileIn, ProgramResultOut
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
        await repo.write_audit(user.user_id, "save_screening", saved.get("id"))
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    return {"id": saved.get("id"), "headline": headline, "summary": s}


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
