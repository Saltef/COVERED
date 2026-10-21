"""Prove row-level security against a running SurrealDB.

    docker compose up -d surrealdb
    python scripts/test_rls.py
"""
from __future__ import annotations

import os

os.environ.setdefault("SURREAL_URL", "ws://localhost:8001/rpc")

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import repository as repo  # noqa: E402
from app.security.auth import Principal, Role  # noqa: E402


async def main() -> None:
    await repo.init_schema()
    s1 = await repo.save_screening("u1", "owed $100", {"first_name": "A"}, [], {"total_estimated_annual": 100})
    s2 = await repo.save_screening("u2", "owed $200", {"first_name": "B"}, [], {"total_estimated_annual": 200})

    p1 = Principal("u1", Role.senior)
    adm = Principal("root", Role.admin)
    care = Principal("care", Role.caregiver)

    own = await repo.get_screening(p1, s1["id"])
    cross = await repo.get_screening(p1, s2["id"])
    admin_all = await repo.list_screenings(adm)

    await repo.grant_access("u1", "care")  # u1 shares with caregiver "care"
    care_granted = await repo.get_screening(care, s1["id"])
    care_ungranted = await repo.get_screening(care, s2["id"])

    print("u1 reads own record:      ", own is not None, "(expect True)")
    print("u1 reads u2's record:     ", cross is not None, "(expect False)")
    print("admin sees all:           ", len(admin_all), "records")
    print("caregiver reads granted:  ", care_granted is not None, "(expect True)")
    print("caregiver reads ungranted:", care_ungranted is not None, "(expect False)")

    ok = (own is not None and cross is None and care_granted is not None and care_ungranted is None)
    print("\nRLS", "OK" if ok else "FAILED")


asyncio.run(main())
