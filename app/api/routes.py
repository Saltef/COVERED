"""HTTP routes.

/screen and /demo require an authenticated principal (in dev, the no-auth fallback supplies one).
Screening itself is a pure function of the posted profile; Claude only adds the plain-language note.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.agents.explainer import explain
from app.api.schemas import ProfileIn, ProgramResultOut, ScreenResponse
from app.config import get_settings
from app.db import repository as repo
from app.domain.rules_engine import screen, summarize
from app.models import Profile
from app.security.auth import Principal, Role, get_current_user
from app.security.authz import require_role
from app.seed.personas import sample_senior

router = APIRouter()


async def _build(profile: Profile) -> ScreenResponse:
    results = screen(profile)
    s = summarize(results)
    headline = (
        f"You could be owed about ${s['total_estimated_annual']:,.0f} a year across "
        f"{s['n_eligible_or_maybe']} programs you may not be getting."
    )
    out = [ProgramResultOut.from_domain(r) for r in results]
    explanation = await explain(headline, out)
    return ScreenResponse(headline=headline, summary=s, results=out, explanation=explanation)


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "surrealdb": await repo.ping()}


@router.get("/config")
async def config() -> dict:
    """Public runtime config for the frontend (which auth to use)."""
    s = get_settings()
    return {"clerk_publishable_key": s.clerk_publishable_key, "auth_required": bool(s.clerk_publishable_key)}


@router.get("/benchmark")
async def benchmark() -> dict:
    """Score the screening agent against ground-truth cases (accuracy, per-program errors)."""
    from app.eval.benchmark import run
    from app.eval.era import fetch_era_cases
    return run(fetch_era_cases())


@router.get("/activity")
async def activity(user: Principal = Depends(get_current_user)) -> list[dict]:
    """Audit trail visible to the caller (own record + own actions; admin sees all)."""
    try:
        return await repo.list_audit(user)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")


@router.get("/agency/caseload")
async def agency_caseload(user: Principal = Depends(require_role(Role.admin))) -> dict:
    """Agency oversight: roll up every screening in the caseload (admin sees all via RLS)."""
    try:
        screenings = await repo.list_screenings(user)
    except repo.SurrealUnavailable as exc:
        raise HTTPException(503, f"storage unavailable ({exc})")
    clients, total = [], 0
    for s in screenings:
        summ = s.get("summary") or {}
        amt = summ.get("total_estimated_annual") or 0
        total += amt
        clients.append({"id": s.get("id"), "name": s.get("name"), "owner": s.get("owner"),
                        "total": amt, "programs": summ.get("n_eligible_or_maybe") or 0,
                        "created_at": s.get("created_at")})
    n = len(clients)
    return {"summary": {"n_clients": n, "total_annual": total, "avg": round(total / n) if n else 0},
            "clients": clients}


@router.get("/era/clients")
async def era_clients() -> dict:
    """Live ingestion: pull the client roster from the Era-simulated agency (caseworker demo)."""
    from app.eval.era import (era_configured, fetch_era_records, record_to_profile,
                              record_display, is_screenable)
    from app.domain.rules_engine import screen, summarize
    from app.models import Profile

    if not era_configured():
        return {"configured": False,
                "detail": "Set ERA_SYSTEM + ERA_RECORDS_PATH and <SYSTEM>_BASE_URL / <SYSTEM>_MCP_HEADER in .env"}
    records = await fetch_era_records()
    roster = []
    for rec in records:
        prof = record_to_profile(rec)
        item = {"name": prof.get("first_name") or "(unknown)",
                "ingested": record_display(rec),
                "screenable": is_screenable(prof)}
        if item["screenable"]:
            item["summary"] = summarize(screen(Profile(**prof)))
        roster.append(item)
    return {
        "configured": True,
        "source": "era:hubspot",
        "n_ingested": len(roster),
        "n_screenable": sum(1 for r in roster if r["screenable"]),
        "note": ("Live-ingested from the Era-simulated agency's HubSpot via its real API. This B2B CRM "
                 "carries no benefit-eligibility fields (income/age/disability/province), so records "
                 "aren't screenable here; screening accuracy is benchmarked separately at /benchmark."),
        "clients": roster,
    }


@router.get("/ops/ask")
async def ops_ask(q: str) -> dict:
    """Ask the agency ops co-pilot one question over the live Era systems."""
    from app.ops import agent as ops_agent
    if not ops_agent.available():
        return {"available": False, "detail": "Needs ANTHROPIC_API_KEY and Era HubSpot configured"}
    result = await ops_agent.answer(q)
    return {"available": True, "question": q, **(result or {})}


@router.get("/ops/benchmark")
async def ops_benchmark() -> dict:
    """Grade the ops co-pilot against ground truth computed from Era's data."""
    from app.ops.benchmark import run
    return await run()


@router.post("/screen", response_model=ScreenResponse)
async def do_screen(
    profile_in: ProfileIn,
    user: Principal = Depends(require_role(Role.senior, Role.caregiver)),
) -> ScreenResponse:
    return await _build(profile_in.to_domain())


@router.get("/demo", response_model=ScreenResponse)
async def demo(user: Principal = Depends(get_current_user)) -> ScreenResponse:
    """Screen the built-in seeded senior persona — the reproducible demo path."""
    return await _build(sample_senior())
