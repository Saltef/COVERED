"""Row-level security (application layer).

Every stored record carries an `owner` (the Clerk user id). A principal may touch a record
only if they own it, an explicit access_grant names them, or they are admin. The SurrealDB
schema enforces the same rule at the database layer (see app/db/schema.surql) — defense in depth.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from app.security.auth import Principal, Role


def assert_can_access(user: Principal, owner_id: str, granted_ids: Optional[set[str]] = None) -> None:
    if user.role is Role.admin:
        return
    if user.user_id == owner_id:
        return
    if granted_ids and user.user_id in granted_ids:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted to access this record")


def owner_filter(user: Principal) -> dict:
    """A query filter that scopes reads to what the principal may see."""
    if user.role is Role.admin:
        return {}
    return {"owner": user.user_id}
