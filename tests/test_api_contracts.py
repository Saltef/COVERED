"""Layer 2 - API contract tests via TestClient. No browser. DB-free unless marked.

Each test pins the shape of one endpoint plus the honesty guarantees (partner-key auth, the
dev-mode flag, source citations, the fail-closed auth gate).
"""
from __future__ import annotations

import pytest

from app.config import Settings
from tests._support import dev, requires_surreal

DEMO_KEY = "demo-partner-key"
SENIOR = {"first_name": "Test", "province": "ON", "age": 71, "annual_net_income": 22000,
          "prescription_costs_annual": 1800, "has_private_dental_insurance": False}


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_config_reports_dev_mode(client):
    d = client.get("/config").json()
    assert d["auth_enforced"] is False
    assert d["dev_mode"] is True


def test_screen_contract(client):
    r = client.post("/screen", json=SENIOR, headers=dev("senior"))
    assert r.status_code == 200
    d = r.json()
    assert d["headline"] and d["rates_verified"]
    assert all("source_url" in p for p in d["results"])
    assert {"total_estimated_annual", "n_eligible_or_maybe"} <= set(d["summary"])


def test_screen_requires_allowed_role(client):
    assert client.post("/screen", json=SENIOR, headers=dev("clinician")).status_code == 403


def test_v1_rejects_missing_or_bad_key(client):
    assert client.post("/v1/eligibility", json={"age": 70}).status_code == 401
    assert client.post("/v1/eligibility", json={"age": 70}, headers={"X-Covered-Key": "nope"}).status_code == 401


def test_v1_contract_and_ordering(client):
    r = client.post("/v1/eligibility", json=SENIOR, headers={"X-Covered-Key": DEMO_KEY})
    assert r.status_code == 200
    d = r.json()
    assert d["api_version"] == "1.0" and d["currency"] == "CAD"
    assert d["rates_verified"] and d["disclaimer"]
    order = ["eligible", "likely", "maybe", "not_eligible"]
    ranks = [order.index(p["eligibility"]) for p in d["programs"]]
    assert ranks == sorted(ranks)  # claimable programs sorted first
    assert all("source_url" in p for p in d["programs"])


def test_benchmark_endpoint_is_perfect(client):
    d = client.get("/benchmark").json()
    assert d["cases_passed"] == d["n_cases"]


@pytest.mark.parametrize("path", ["/", "/caregiver", "/clinician", "/agency", "/pharmacy", "/tax", "/developers"])
def test_pages_served(client, path):
    r = client.get(path)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_auth_gate_fails_closed_outside_development():
    Settings(app_env="development", dev_allow_no_auth=True).assert_auth_safe()  # must not raise
    for env in ("staging", "production"):
        with pytest.raises(RuntimeError):
            Settings(app_env=env, dev_allow_no_auth=True).assert_auth_safe()


def test_homecare_screen_contract(client):
    r = client.post("/homecare/screen", json={"age": 68, "permanent_physical_disability": True,
        "tasks": ["bathing", "household"], "needs_stable_1yr": True, "can_self_manage": True,
        "hours_per_week": 20})
    assert r.status_code == 200
    d = r.json()
    assert d["eligibility"] == "likely"
    assert d["monthly_budget"] > 0
    assert d["source_url"].startswith("https://www.dfontario.ca")
    assert len(d["application"]) == 8


@requires_surreal
def test_book_stats_requires_admin(client):
    assert client.get("/agency/book-stats", headers=dev("senior")).status_code == 403
    r = client.get("/agency/book-stats", headers=dev("admin"))
    assert r.status_code == 200 and "n_clients" in r.json()
