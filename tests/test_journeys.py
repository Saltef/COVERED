"""Layer 3 - persona journeys end to end (require SurrealDB).

Each test walks one persona through several features, which is where integration bugs surface.
Writes use random dev-user ids so runs do not collide with seeded data or each other.
"""
from __future__ import annotations

from tests._support import dev, requires_surreal, uniq

pytestmark = requires_surreal

MARGARET = {"first_name": "Margaret", "province": "ON", "age": 71, "annual_net_income": 28500,
            "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 3500,
            "prescription_costs_annual": 1800, "has_severe_prolonged_impairment": True}


def test_senior_apply_produces_pdf(client):
    pkgs = client.post("/apply", json=MARGARET, headers=dev("senior")).json()
    assert isinstance(pkgs, list) and pkgs
    pid = pkgs[0]["program_id"]
    r = client.post(f"/apply/{pid}/pdf", json=MARGARET, headers=dev("senior"))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_rls_isolation_between_patients(client):
    a, b = uniq("pa"), uniq("pb")
    created = client.post("/me/screenings", json=MARGARET, headers=dev("caregiver", a)).json()
    sid = created.get("id")
    assert sid
    a_ids = {s.get("id") for s in client.get("/me/screenings", headers=dev("caregiver", a)).json()}
    b_ids = {s.get("id") for s in client.get("/me/screenings", headers=dev("caregiver", b)).json()}
    assert sid in a_ids and sid not in b_ids
    assert client.get(f"/me/screenings/{sid}", headers=dev("caregiver", b)).status_code in (403, 404)


def test_care_team_part_b_loop(client):
    patient, doc = uniq("pt"), uniq("dr") + "@clinic.test"
    client.post("/me/screenings", json=MARGARET, headers=dev("caregiver", patient))
    client.post("/me/care-team/invite",
                json={"email": doc, "role": "clinician", "scope": ["read", "medical"]},
                headers=dev("caregiver", patient))
    v = client.post("/clinician/verify",
                    json={"full_name": "Dr. Test", "license_number": "1", "college": "CPSO", "province": "ON"},
                    headers=dev("clinician", doc)).json()
    assert v["status"] == "verified"
    pend = client.get("/clinician/pending", headers=dev("clinician", doc)).json().get("pending", [])
    assert pend, "clinician should see the patient's DTC case"
    sid = pend[0]["screening_id"]
    att = client.post("/attestations",
                      json={"screening_id": sid, "cra_reference_number": "DTC-REF-1", "fields": {"certified": True}},
                      headers=dev("clinician", doc)).json()
    assert att.get("status") == "attested"


def test_agency_book_rollup(client):
    cw = uniq("cw")
    for p in (MARGARET, {**MARGARET, "first_name": "Robert", "province": "BC"}):
        client.post("/me/screenings", json=p, headers=dev("support_worker", cw))
    stats = client.get("/agency/book-stats", headers=dev("admin")).json()
    assert stats["n_clients"] >= 2
    assert stats["total_unclaimed_annual"] >= 0
    assert isinstance(stats["program_counts"], dict)
