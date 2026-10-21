"""API smoke test using FastAPI's TestClient (no running server needed).

    python scripts/smoke_api.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

c = TestClient(app)

h = c.get("/healthz")
print("healthz:", h.status_code, h.json())

d = c.get("/demo")
print("demo:", d.status_code)
body = d.json()
print("headline:", body["headline"])
for r in body["results"]:
    if r["eligibility"] in ("eligible", "likely", "maybe"):
        val = f"${r['estimated_annual_value']:,.0f}" if r["estimated_annual_value"] else "-"
        print(f"  {r['eligibility']:>12}  {r['program_name']:<34} {val}")

s = c.post(
    "/screen",
    json={"province": "ON", "age": 45, "annual_net_income": 20000, "has_severe_prolonged_impairment": True},
    headers={"X-Dev-Role": "caregiver"},
)
print("screen(caregiver):", s.status_code, "->", s.json()["headline"])

print("\n-- interview (M2) --")
sc = c.get("/interview/script")
print("script:", sc.status_code, len(sc.json()), "questions")
cases = [
    ("annual_net_income", "twenty eight thousand five hundred", 28500),
    ("age", "seventy one", 71),
    ("province", "I live in Ontario", "ON"),
    ("has_private_dental_insurance", "no, I don't", False),
    ("first_name", "my name is Margaret", "Margaret"),
]
parse_ok = True
for field, text, expected in cases:
    p = c.post("/interview/parse", json={"field": field, "text": text}).json()
    ok = p["value"] == expected
    parse_ok = parse_ok and ok
    print(f"  {'ok ' if ok else 'BAD'} {field}: '{text}' -> {p['value']}   | {p['confirmation']}")

tr = c.post("/voice/transcribe", files={"file": ("a.webm", b"\x00\x01", "audio/webm")})
print("transcribe:", tr.status_code, tr.json())
root = c.get("/")
print("index /:", root.status_code, root.headers.get("content-type"))

print("\n-- apply (M4) --")
senior = {
    "first_name": "Margaret", "province": "ON", "age": 71, "annual_net_income": 28500,
    "has_private_dental_insurance": False, "out_of_pocket_medical_annual": 3500,
    "prescription_costs_annual": 1800, "has_severe_prolonged_impairment": True, "filed_taxes_last_year": True,
}
ap = c.post("/apply", json=senior)
pkgs = ap.json()
print("apply:", ap.status_code, "-> packages:", [p["program_id"] for p in pkgs])
for p in pkgs:
    pre = sum(1 for f in p["fields"] if f["who"] == "prefilled")
    print(f"  {p['program_id']}: {p['form_name']}  ({pre}/{len(p['fields'])} pre-filled)")
pdf = c.post("/apply/dtc/pdf", json=senior)
magic = pdf.content[:5]
print("dtc pdf:", pdf.status_code, pdf.headers.get("content-type"), "magic:", magic, f"({len(pdf.content)} bytes)")

print("\n-- persistence + config (M3) --")
cfg = c.get("/config")
print("config:", cfg.status_code, cfg.json())
saved = c.post("/me/screenings", json=senior)
print("save screening:", saved.status_code, "-> id:", saved.json().get("id") if saved.status_code == 200 else saved.json())
mine = c.get("/me/screenings")
listed = mine.json() if mine.status_code == 200 else mine.json()
print("list screenings:", mine.status_code, "-> count:", len(listed) if isinstance(listed, list) else listed)
persist_ok = saved.status_code == 200 and mine.status_code == 200 and isinstance(listed, list) and len(listed) >= 1

all_ok = (h.status_code == d.status_code == s.status_code == sc.status_code == tr.status_code
          == root.status_code == ap.status_code == pdf.status_code == cfg.status_code == 200) \
    and parse_ok and magic == b"%PDF-" and persist_ok
print("\nOK" if all_ok else "\nFAILED")
