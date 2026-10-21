"""End-to-end test of the patient care-team + clinician Part B loop (needs SurrealDB up)."""
from __future__ import annotations

import os

os.environ.setdefault("SURREAL_URL", "ws://localhost:8001/rpc")

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

import asyncio  # noqa: E402

from app.db.repository import init_schema  # noqa: E402

asyncio.run(init_schema())  # TestClient doesn't run startup; the live server does

c = TestClient(app)
PATIENT = {"X-Dev-User": "patient-1", "X-Dev-Role": "senior"}
DOCTOR = {"X-Dev-User": "dr.lee@clinic.ca", "X-Dev-Role": "clinician"}

prof = {"first_name": "Margaret", "province": "ON", "age": 71, "annual_net_income": 28500,
        "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 3500,
        "prescription_costs_annual": 1800, "has_severe_prolonged_impairment": True, "filed_taxes_last_year": True}
sc = c.post("/me/screenings", json=prof, headers=PATIENT)
print("patient saves screening:", sc.status_code, "->", sc.json().get("id"))

inv = c.post("/me/care-team/invite",
             json={"email": "dr.lee@clinic.ca", "role": "clinician", "scope": ["read", "medical"]},
             headers=PATIENT)
print("patient invites doctor:  ", inv.status_code, "->", inv.json().get("id"))
team = c.get("/me/care-team", headers=PATIENT).json()
print("care team size:          ", len(team))

print("\n-- doctor --")
before = c.get("/clinician/me", headers=DOCTOR).json()
print("before verify:           ", before.get("status"))
ver = c.post("/clinician/verify",
             json={"full_name": "Dr. Jane Lee", "license_number": "CPSO-12345", "college": "CPSO", "province": "ON"},
             headers=DOCTOR).json()
print("after verify:            ", ver.get("status"))

pend = c.get("/clinician/pending", headers=DOCTOR).json()
print("pending (verified):      ", pend.get("verified"), "| items:", len(pend.get("pending", [])))
item = (pend.get("pending") or [None])[0]
if item:
    print("  patient:", item["patient_name"], "| DTC:", item["dtc"]["eligibility"],
          "| Part B sections:", len(item["partb"]["sections_to_complete"]))

att = c.post("/attestations",
             json={"screening_id": item["screening_id"], "cra_reference_number": "DTC-REF-123",
                   "fields": {"nature": "mental functions", "duration": "prolonged"}},
             headers=DOCTOR)
print("attest Part B:           ", att.status_code, "->", att.json().get("status"),
      "ref:", att.json().get("cra_reference_number"))
att_id = att.json().get("id")
sub = c.post(f"/attestations/{att_id}/mark-submitted", headers=DOCTOR)
print("mark submitted in CRA:   ", sub.status_code)

pend2 = c.get("/clinician/pending", headers=DOCTOR).json()
final = (pend2.get("pending") or [{}])[0].get("attestation") or {}
print("attestation status now:  ", final.get("status"))

ok = (sc.status_code == 200 and inv.status_code == 200 and ver.get("status") == "verified"
      and pend.get("verified") and item and att.status_code == 200
      and att.json().get("status") == "attested" and final.get("status") == "submitted_in_cra")
print("\nCARE-TEAM", "OK" if ok else "FAILED")
