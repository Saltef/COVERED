"""Authorization: role-based access control (RBAC) as FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.security.auth import Principal, Role, get_current_user


def require_role(*allowed: Role):
    """Dependency factory: allow the listed roles (admin is always allowed)."""

    async def _dependency(user: Principal = Depends(get_current_user)) -> Principal:
        if user.role is not Role.admin and user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role for this action")
        return user

    return _dependency
