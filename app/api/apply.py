"""The 'apply' step: prepare ready-to-submit application packages (JSON + PDF)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from app.api.schemas import ProfileIn
from app.domain.applications import build_packages, get_package, package_to_dict
from app.domain.rules_engine import screen
from app.security.auth import Principal, get_current_user

router = APIRouter()


@router.post("/apply")
async def apply(profile_in: ProfileIn, user: Principal = Depends(get_current_user)) -> list[dict]:
    profile = profile_in.to_domain()
    results = screen(profile)
    return [package_to_dict(p) for p in build_packages(profile, results)]


@router.post("/apply/{program_id}/pdf")
async def apply_pdf(
    program_id: str,
    profile_in: ProfileIn,
    user: Principal = Depends(get_current_user),
):
    pkg = get_package(program_id, profile_in.to_domain())
    if pkg is None:
        return JSONResponse({"error": f"no application form for program: {program_id}"}, status_code=404)
    try:
        from app.services.pdf import render_package_pdf
        pdf = render_package_pdf(pkg)
    except Exception as exc:  # noqa: BLE001 — reportlab missing or render error
        return JSONResponse({"error": f"PDF unavailable: {type(exc).__name__}"}, status_code=503)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{program_id}-application.pdf"'},
    )
