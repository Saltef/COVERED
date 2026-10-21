"""Authentication via Clerk (OIDC/JWT).

We verify Clerk-issued JWTs locally with the Clerk PEM public key (CLERK_JWT_KEY) — no
password ever touches this service. In local development, when DEV_ALLOW_NO_AUTH is set and
we are not in production, unauthenticated requests are given a dev identity so the team can
work without a Clerk project. That fallback is hard-disabled in production.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings

log = logging.getLogger(__name__)


class Role(str, Enum):
    senior = "senior"
    caregiver = "caregiver"
    admin = "admin"


@dataclass
class Principal:
    user_id: str
    role: Role
    org_id: Optional[str] = None
    is_dev: bool = False


def _map_role(raw: Optional[str]) -> Role:
    raw = (raw or "").lower()
    if "admin" in raw:
        return Role.admin
    if "caregiver" in raw:
        return Role.caregiver
    return Role.senior


def _verify_clerk_jwt(token: str, settings: Settings) -> Principal:
    if not settings.clerk_jwt_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is not configured")
    try:
        import jwt  # lazy import so the app loads without the dependency installed
        claims = jwt.decode(
            token,
            settings.clerk_jwt_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except Exception as exc:  # noqa: BLE001 — never leak verifier internals
        log.warning("JWT verification failed: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing subject")

    org = claims.get("o") or {}
    role_claim = claims.get("covered_role") or org.get("rol")
    return Principal(user_id=user_id, role=_map_role(role_claim), org_id=org.get("id"))


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    x_dev_role: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        return _verify_clerk_jwt(token, settings)

    if settings.dev_allow_no_auth and not settings.is_production:
        return Principal(user_id="dev-user", role=_map_role(x_dev_role), is_dev=True)

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
