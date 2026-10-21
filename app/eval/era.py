"""Era by Eon adapter.

Era by Eon generates a simulated company whose systems (HubSpot, Salesforce, Zendesk, ...) speak
their real vendor REST/MCP APIs, with per-system env vars written by the `era` CLI:
    <SYSTEM>_BASE_URL, <SYSTEM>_MCP_URL, <SYSTEM>_MCP_HEADER

Era's ground-truth "answer keys" score ENTERPRISE questions and its records are CRM contacts/
accounts/tickets — they carry no income / age / disability / province. So Era cannot supply
benefit-eligibility labels: fetch_era_cases() stays None and accuracy is measured on the built-in
hand-labeled ground truth (app/eval/ground_truth.py).

What Era is used for here (the "caseworker" integration): pull a population of people from the
agency's simulated CRM and screen each with our engine. Configure in .env:
    ERA_SYSTEM=hubspot
    ERA_RECORDS_PATH=/crm/v3/objects/contacts
    HUBSPOT_BASE_URL=...        (written by the era CLI)
    HUBSPOT_MCP_HEADER=Authorization: Bearer ...   (written by the era CLI)

FIELD_MAP must be finalized from a real record (run scripts/era_probe.py and inspect the fields).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

_ENV_LOADED = False


def _ensure_env() -> None:
    """Load .env into os.environ so the per-system vars (e.g. HUBSPOT_BASE_URL) are visible.
    (pydantic-settings reads .env into Settings but doesn't export arbitrary vars to os.environ.)"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    _ENV_LOADED = True


def _system() -> tuple[str, str]:
    from app.config import get_settings
    s = get_settings()
    return s.era_system.strip(), s.era_records_path.strip()


def _conn() -> Optional[tuple[str, str, str]]:
    _ensure_env()
    system, path = _system()
    if not system:
        return None
    base = os.environ.get(f"{system.upper()}_BASE_URL", "").strip()
    header = os.environ.get(f"{system.upper()}_MCP_HEADER", "").strip()
    if not base:
        return None
    return base, path, header


def era_configured() -> bool:
    return _conn() is not None


def _header_dict(header_spec: str) -> dict:
    if header_spec and ":" in header_spec:
        name, value = header_spec.split(":", 1)
        return {name.strip(): value.strip()}
    return {}


async def fetch_era_records(limit: int = 25) -> list[dict]:
    """GET the configured system's records collection and return the raw record dicts."""
    conn = _conn()
    if conn is None:
        return []
    base, path, header = conn
    import httpx

    url = base.rstrip("/") + "/" + path.lstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=_header_dict(header), params={"limit": limit})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.info("Era fetch failed: %s", type(exc).__name__)
        return []
    if isinstance(data, dict):
        for key in ("results", "records", "data", "items", "value"):
            if isinstance(data.get(key), list):
                return data[key]
        return []
    return data if isinstance(data, list) else []


# --- field mapping (finalized against the real Era HubSpot schema) ---
# Era's simulated HubSpot is a B2B SaaS CRM: its 124 contact properties are sales/marketing
# fields (arr, mrr, churn_risk, utm_*, US country/state ...) with NONE of our benefit-eligibility
# inputs (net income, age, disability, Canadian province, dental insurance, drug costs). So only
# the name maps; the records are ingestable but not screenable. record_display() surfaces the
# real fields that ARE present, for the live-ingestion demo.
FIELD_MAP: dict[str, str] = {
    "first_name": "properties.firstname",
}

# screening needs at least these; Era's CRM has neither, so Era records are not screenable.
SCREENABLE_REQUIRED = ("age", "annual_net_income")
DISPLAY_FIELDS = ["email", "country", "state", "plan_name", "lifecyclestage", "churn_risk", "jobtitle"]


def _dig(record: dict, dotted: str):
    cur = record
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def record_to_profile(record: dict) -> dict:
    """Map one Era record to a Profile dict using FIELD_MAP."""
    profile: dict = {}
    for field, path in FIELD_MAP.items():
        value = _dig(record, path)
        if value is not None:
            profile[field] = value
    return profile


def record_display(record: dict) -> dict:
    """The real fields present on an Era record (for the live-ingestion demo)."""
    out = {}
    for key in DISPLAY_FIELDS:
        value = _dig(record, "properties." + key)
        if value is not None:
            out[key] = value
    return out


def is_screenable(profile: dict) -> bool:
    return all(profile.get(f) for f in SCREENABLE_REQUIRED)


def fetch_era_cases() -> Optional[list[dict]]:
    """Era has no benefit-eligibility answer keys, so it cannot label {profile, expected_actionable}.
    Returns None; the benchmark uses the built-in hand-labeled ground truth."""
    return None
