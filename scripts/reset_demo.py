"""Wipe accumulated test data and seed ONE coherent demo set (needs SurrealDB up).

    python scripts/reset_demo.py

Clears screenings, grants, clinician profiles, attestations, statuses, and the audit log, then seeds
three clean clients (owned by the caregiver 'dev-user') and invites a doctor to the care team, so the
caregiver / clinician / agency views all show tidy, consistent data.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("SURREAL_URL", "ws://localhost:8001/rpc")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.repository import _db, init_schema  # noqa: E402

_TABLES = ["screening", "care_team_grant", "clinician_profile", "attestation",
           "program_status", "audit_log", "access_grant"]


async def _clear() -> None:
    await init_schema()
    async with _db() as db:
        for t in _TABLES:
            await db.query(f"DELETE {t};")


def main() -> None:
    asyncio.run(_clear())
    print("Cleared:", ", ".join(_TABLES))

    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    care = {"X-Dev-Role": "caregiver"}  # identity = dev-user

    clients = [
        {"first_name": "Margaret", "province": "ON", "age": 71, "annual_net_income": 28_500,
         "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 3_500,
         "prescription_costs_annual": 1_800, "has_severe_prolonged_impairment": True, "filed_taxes_last_year": True},
        {"first_name": "Robert", "province": "ON", "age": 68, "annual_net_income": 24_000,
         "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 4_200,
         "prescription_costs_annual": 2_500, "has_severe_prolonged_impairment": True, "filed_taxes_last_year": True},
        {"first_name": "Elaine", "province": "BC", "age": 59, "annual_net_income": 41_000,
         "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 1_200,
         "prescription_costs_annual": 300, "is_caregiver": True, "filed_taxes_last_year": True},
    ]
    for p in clients:
        r = c.post("/me/screenings", json=p, headers=care)
        print(f"  seeded {p['first_name']:<9} {r.status_code} -> {r.json().get('headline', '')[:60]}")

    c.post("/me/care-team/invite",
           json={"email": "dr.lee@clinic.ca", "role": "clinician", "scope": ["read", "medical"]}, headers=care)
    print("  invited dr.lee@clinic.ca to the care team")
    print("\nDONE — clean demo data seeded.")


if __name__ == "__main__":
    main()
