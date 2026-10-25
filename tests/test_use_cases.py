"""10 diverse, functionality-focused use cases over the full system.

Each case is unique, carries several data points, and exercises a distinct piece of functionality:
the engine's breadth, the DTC unlock chain, the drug-coverage age bands, province gating, the
income-independent ODB, the home-care Direct Funding vs atHome fork, the partner embed API, the
apply/PDF package, and the honesty layer (sources + verified date + benchmark).
"""
from __future__ import annotations

from app.api.schemas import ProfileIn
from app.domain import direct_funding as df
from app.domain.programs import SOURCES
from app.domain.rules_engine import screen
from tests._support import dev

ACTIONABLE = {"eligible", "likely", "maybe"}
DEMO_KEY = "demo-partner-key"


def _results(**fields):
    return {r.program_id: r for r in screen(ProfileIn(**fields).to_domain())}


def _actionable(**fields):
    return {pid for pid, r in _results(**fields).items() if r.eligibility.value in ACTIONABLE}


# 1. Low-income senior, full stack: many programs stack, and Trillium is correctly suppressed at 65+.
def test_case_01_low_income_senior_full_stack():
    got = _actionable(province="ON", age=71, annual_net_income=28_500, has_private_dental_insurance=False,
                      out_of_pocket_medical_annual=3_500, prescription_costs_annual=1_800,
                      has_severe_prolonged_impairment=True)
    assert got == {"dtc", "cdcp", "metc", "odb", "adp"}
    assert "otdp" not in got  # 65+ uses ODB, not Trillium


# 2. DTC unlock chain: the DTC opens the Canada Disability Benefit and the RDSP.
def test_case_02_dtc_unlock_chain():
    r = _results(province="ON", age=45, annual_net_income=18_000, has_dtc_certificate=True,
                 has_severe_prolonged_impairment=True)
    assert r["dtc"].eligibility.value == "eligible"
    assert r["cdb"].eligibility.value in ACTIONABLE and r["rdsp"].eligibility.value in ACTIONABLE
    assert r["cdb"].unlocked_by == "dtc" and r["rdsp"].unlocked_by == "dtc"


# 3. Drug-coverage age bands: under 25 OHIP+, 25-64 Trillium, 65+ ODB; exactly one per age.
def test_case_03_drug_coverage_age_bands():
    youth = _results(province="ON", age=20, prescription_costs_annual=2_000)
    mid = _results(province="ON", age=50, prescription_costs_annual=2_000, annual_net_income=20_000)
    senior = _results(province="ON", age=70, prescription_costs_annual=2_000)
    fired = lambda r: {p for p in ("ohipplus", "otdp", "odb") if r[p].eligibility.value in ACTIONABLE}
    assert fired(youth) == {"ohipplus"}
    assert fired(mid) == {"otdp"}
    assert fired(senior) == {"odb"}


# 4. Province gating: the same person in BC loses every Ontario program.
def test_case_04_province_gating():
    base = dict(age=70, annual_net_income=20_000, has_private_dental_insurance=False,
                out_of_pocket_medical_annual=3_000, prescription_costs_annual=1_500,
                has_severe_prolonged_impairment=True)
    on = _actionable(province="ON", **base)
    bc = _actionable(province="BC", **base)
    assert {"odb", "adp"} <= on and not ({"odb", "adp", "otdp", "ohipplus"} & bc)
    assert "dtc" in bc and "cdcp" in bc  # federal programs still apply in BC


# 5. ODB is not income-tested: a high-income senior still qualifies, and only for ODB.
def test_case_05_odb_not_income_tested():
    assert _actionable(province="ON", age=70, annual_net_income=200_000,
                       has_private_dental_insurance=True) == {"odb"}


# 6. Home-care fork, self-manager: Direct Funding is recommended with a real budget.
def test_case_06_home_care_direct_funding(client):
    r = client.post("/homecare/screen", json={"age": 62, "permanent_physical_disability": True,
        "tasks": ["bathing", "dressing"], "needs_stable_1yr": True, "can_self_manage": True,
        "hours_per_week": 20}).json()
    assert r["recommended"] == "direct_funding"
    assert r["direct_funding"]["eligibility"] == "likely"
    assert r["direct_funding"]["monthly_budget"] > 0


# 7. Home-care fork, cannot self-manage: Ontario Health atHome is recommended instead.
def test_case_07_home_care_athome(client):
    r = client.post("/homecare/screen", json={"age": 80, "permanent_physical_disability": True,
        "tasks": ["bathing", "toileting"], "needs_stable_1yr": True, "can_self_manage": False}).json()
    assert r["recommended"] == "athome"
    assert r["athome"]["fit"] is True and r["athome"]["services"]


# 8. Partner embed API: key auth, the versioned contract, claimable-first ordering, source links.
def test_case_08_partner_embed_api(client):
    assert client.post("/v1/eligibility", json={"age": 72}).status_code == 401  # no key
    r = client.post("/v1/eligibility", json={"age": 72, "province": "ON", "annual_net_income": 24_000,
        "prescription_costs_annual": 1_800, "has_private_dental_insurance": False},
        headers={"X-Covered-Key": DEMO_KEY})
    assert r.status_code == 200
    d = r.json()
    assert d["api_version"] == "1.0" and d["rates_verified"]
    order = ["eligible", "likely", "maybe", "not_eligible"]
    ranks = [order.index(p["eligibility"]) for p in d["programs"]]
    assert ranks == sorted(ranks)
    assert all("source_url" in p for p in d["programs"])


# 9. Apply and PDF: a screened senior gets ready-to-prepare packages and a real PDF.
def test_case_09_apply_and_pdf(client):
    profile = {"first_name": "Grace", "province": "ON", "age": 71, "annual_net_income": 26_000,
               "has_private_dental_insurance": False, "prescription_costs_annual": 1_500,
               "has_severe_prolonged_impairment": True}
    pkgs = client.post("/apply", json=profile, headers=dev("senior")).json()
    assert isinstance(pkgs, list) and pkgs
    pid = pkgs[0]["program_id"]
    pdf = client.post(f"/apply/{pid}/pdf", json=profile, headers=dev("senior"))
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


# 10. Honesty layer: every program has a source, the screen carries a verified date, benchmark is perfect.
def test_case_10_honesty_layer(client):
    d = client.post("/screen", json={"first_name": "T", "province": "ON", "age": 71,
        "annual_net_income": 22_000, "prescription_costs_annual": 1_800}, headers=dev("senior")).json()
    assert d["rates_verified"]
    assert all(r.get("source_url") for r in d["results"])
    from app.eval.benchmark import run
    b = run(None)
    assert b["cases_passed"] == b["n_cases"] and b["decision_accuracy"] == 1.0
