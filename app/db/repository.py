"""SurrealDB repository with application-layer row-level security.

Every read/write is scoped to the authenticated principal: a person sees only records they own,
plus records whose owner granted them access (caregiver), while an admin sees all. The SurrealDB
schema (schema.surql) declares the same ownership policy at the database layer for defense in depth.

All operations degrade safely: if SurrealDB is unavailable, SurrealUnavailable is raised and the
caller returns a 503 rather than crashing.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from app.config import get_settings
from app.security.auth import Principal, Role

log = logging.getLogger(__name__)


class SurrealUnavailable(RuntimeError):
    pass


@asynccontextmanager
async def _db():
    settings = get_settings()
    try:
        from surrealdb import AsyncSurreal
    except Exception as exc:  # noqa: BLE001
        raise SurrealUnavailable("client-not-installed") from exc
    try:
        async with AsyncSurreal(settings.surreal_url) as db:
            await db.signin({"username": settings.surreal_user, "password": settings.surreal_pass})
            await db.use(settings.surreal_ns, settings.surreal_db)
            yield db
    except SurrealUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        log.info("SurrealDB unavailable: %s", type(exc).__name__)
        raise SurrealUnavailable(type(exc).__name__) from exc


def _rows(res) -> list:
    if res is None:
        return []
    return res if isinstance(res, list) else [res]


def _clean(row):
    if not isinstance(row, dict):
        return row
    out = dict(row)
    for k in ("id", "created_at", "at"):
        if out.get(k) is not None:
            out[k] = str(out[k])
    return out


def _bare_id(rid: str) -> str:
    return rid.split(":", 1)[1] if ":" in rid else rid


async def ping() -> str:
    try:
        async with _db() as db:
            await db.query("RETURN 1;")
        return "connected"
    except SurrealUnavailable as exc:
        return str(exc)


_INIT_SQL = (
    "DEFINE TABLE IF NOT EXISTS person SCHEMALESS;"
    "DEFINE TABLE IF NOT EXISTS screening SCHEMALESS;"
    "DEFINE TABLE IF NOT EXISTS access_grant SCHEMALESS;"
    "DEFINE TABLE IF NOT EXISTS audit_log SCHEMALESS;"
    "DEFINE TABLE IF NOT EXISTS care_team_grant SCHEMALESS;"
    "DEFINE TABLE IF NOT EXISTS clinician_profile SCHEMALESS;"
    "DEFINE TABLE IF NOT EXISTS attestation SCHEMALESS;"
)


async def init_schema() -> None:
    """Ensure the core tables exist (idempotent). Safe to call on every startup."""
    async with _db() as db:
        await db.query(_INIT_SQL)


async def save_screening(owner_id: str, headline: str, profile: dict, results: list, summary: dict) -> dict:
    name = (profile.get("first_name") or "").strip() or "(unnamed)"
    async with _db() as db:
        res = await db.query(
            "CREATE screening SET owner=$o, name=$n, headline=$h, profile=$p, results=$r, summary=$s, "
            "created_at=time::now();",
            {"o": owner_id, "n": name, "h": headline, "p": profile, "r": results, "s": summary},
        )
        rows = _rows(res)
        return _clean(rows[0]) if rows else {}


async def list_screenings(principal: Principal) -> list[dict]:
    async with _db() as db:
        if principal.role is Role.admin:
            res = await db.query(
                "SELECT id, owner, name, headline, summary, created_at FROM screening ORDER BY created_at DESC;")
        else:
            res = await db.query(
                "SELECT id, owner, name, headline, summary, created_at FROM screening "
                "WHERE owner = $o OR owner IN (SELECT VALUE grantor FROM access_grant WHERE grantee = $o) "
                "ORDER BY created_at DESC;",
                {"o": principal.user_id},
            )
        return [_clean(r) for r in _rows(res)]


async def get_screening(principal: Principal, rid: str) -> Optional[dict]:
    from surrealdb import RecordID

    async with _db() as db:
        res = await db.query(
            "SELECT * FROM screening WHERE id = $rid AND "
            "($admin OR owner = $o OR owner IN (SELECT VALUE grantor FROM access_grant WHERE grantee = $o));",
            {"rid": RecordID("screening", _bare_id(rid)), "o": principal.user_id,
             "admin": principal.role is Role.admin},
        )
        rows = _rows(res)
        return _clean(rows[0]) if rows else None


async def grant_access(grantor_id: str, grantee_id: str) -> None:
    async with _db() as db:
        await db.query(
            "CREATE access_grant SET grantor=$g, grantee=$e, scope='read';",
            {"g": grantor_id, "e": grantee_id},
        )


async def write_audit(actor_id: str, action: str, subject: Optional[str] = None) -> None:
    try:
        async with _db() as db:
            await db.query(
                "CREATE audit_log SET actor=$a, action=$act, subject=$s, at=time::now();",
                {"a": actor_id, "act": action, "s": subject},
            )
    except SurrealUnavailable:
        pass  # auditing must never break the request
