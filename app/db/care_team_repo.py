"""Repository for the patient-centric care team: grants, clinician verification, attestations.

Builds on app/db/repository.py (connection + helpers). All operations degrade via SurrealUnavailable.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.db.repository import SurrealUnavailable, _clean, _db, _rows, write_audit

log = logging.getLogger(__name__)

_ACTIONABLE = ("eligible", "likely", "maybe")


# ---------- care-team grants (the patient invites members) ----------
async def invite_member(patient_id: str, email: str, role: str, scope: list[str]) -> dict:
    async with _db() as db:
        res = await db.query(
            "CREATE care_team_grant SET patient=$p, member_email=$e, role=$r, scope=$s, "
            "status='invited', created_at=time::now();",
            {"p": patient_id, "e": (email or "").lower().strip(), "r": role, "s": scope},
        )
        rows = _rows(res)
        return _clean(rows[0]) if rows else {}


async def list_care_team(patient_id: str) -> list[dict]:
    async with _db() as db:
        res = await db.query(
            "SELECT * FROM care_team_grant WHERE patient=$p ORDER BY created_at DESC;", {"p": patient_id})
        return [_clean(r) for r in _rows(res)]


async def revoke_grant(patient_id: str, grant_id: str) -> None:
    from surrealdb import RecordID
    rid = RecordID("care_team_grant", grant_id.split(":", 1)[-1])
    async with _db() as db:
        await db.query("UPDATE care_team_grant SET status='revoked' WHERE id=$rid AND patient=$p;",
                       {"rid": rid, "p": patient_id})


# ---------- clinician verification (stub verifier) ----------
def _verify_license(full_name: str, license_number: str, college: str, province: str) -> dict:
    # StubVerifier: approves when the basics are present. RegistryVerifier (real provincial-college
    # register lookup) is the documented integration point — colleges have public registers, no clean API.
    ok = bool(full_name and license_number and (college or province))
    return {"verified": ok, "method": "stub"}


async def verify_clinician(member_id: str, full_name: str, license_number: str,
                           college: str, province: str) -> dict:
    result = _verify_license(full_name, license_number, college, province)
    status = "verified" if result["verified"] else "rejected"
    async with _db() as db:
        await db.query("DELETE clinician_profile WHERE member_id=$m;", {"m": member_id})
        res = await db.query(
            "CREATE clinician_profile SET member_id=$m, full_name=$n, license_number=$l, college=$c, "
            "province=$pr, status=$s, method=$meth, verified_at=time::now();",
            {"m": member_id, "n": full_name, "l": license_number, "c": college, "pr": province,
             "s": status, "meth": result["method"]},
        )
        rows = _rows(res)
    await write_audit(member_id, "verify", member_id,
                      f"{full_name} verified ({college or province})" if status == "verified"
                      else "License verification rejected")
    return _clean(rows[0]) if rows else {}


async def get_clinician_profile(member_id: str) -> Optional[dict]:
    async with _db() as db:
        res = await db.query("SELECT * FROM clinician_profile WHERE member_id=$m LIMIT 1;", {"m": member_id})
        rows = _rows(res)
        return _clean(rows[0]) if rows else None


async def is_verified_clinician(member_id: str) -> bool:
    prof = await get_clinician_profile(member_id)
    return bool(prof and prof.get("status") == "verified")


# ---------- attestations (Part B coordination; CRA owns submission) ----------
async def _has_medical_access(member_email: str, patient_id: str) -> bool:
    async with _db() as db:
        res = await db.query(
            "SELECT id FROM care_team_grant WHERE member_email=$e AND patient=$p AND status='active' "
            "AND 'medical' IN scope LIMIT 1;",
            {"e": member_email, "p": patient_id})
        return bool(_rows(res))


async def list_clinician_pending(member_email: str) -> list[dict]:
    async with _db() as db:
        # a clinician viewing their queue activates any pending invitations to them
        await db.query(
            "UPDATE care_team_grant SET status='active' WHERE member_email=$e AND status='invited' "
            "AND 'medical' IN scope;", {"e": member_email})
        g = await db.query(
            "SELECT VALUE patient FROM care_team_grant WHERE member_email=$e AND status='active' "
            "AND 'medical' IN scope;", {"e": member_email})
        patients = list({p for p in _rows(g) if p})
        if not patients:
            return []
        s = await db.query(
            "SELECT id, owner, name, profile, results, created_at FROM screening "
            "WHERE owner IN $pts ORDER BY created_at DESC;", {"pts": patients})
        out: list[dict] = []
        for rec in _rows(s):
            rec = _clean(rec)
            dtc = next((r for r in (rec.get("results") or []) if r.get("program_id") == "dtc"), None)
            if not dtc or dtc.get("eligibility") not in _ACTIONABLE:
                continue
            att = await db.query(
                "SELECT * FROM attestation WHERE screening=$sid ORDER BY attested_at DESC LIMIT 1;",
                {"sid": rec.get("id")})
            arows = _rows(att)
            out.append({
                "screening_id": rec.get("id"), "patient_name": rec.get("name"),
                "profile": rec.get("profile"), "dtc": dtc,
                "attestation": _clean(arows[0]) if arows else None,
            })
        return out


async def create_attestation(clinician_email: str, screening_id: str, fields: dict,
                             cra_reference_number: str) -> Optional[dict]:
    from surrealdb import RecordID
    srid = RecordID("screening", screening_id.split(":", 1)[-1])
    async with _db() as db:
        sres = await db.query("SELECT owner FROM screening WHERE id=$rid LIMIT 1;", {"rid": srid})
        srows = _rows(sres)
        if not srows:
            return None
        owner = _clean(srows[0]).get("owner")
    if not await _has_medical_access(clinician_email, owner):
        return {"error": "no medical access to this patient"}
    async with _db() as db:
        res = await db.query(
            "CREATE attestation SET screening=$sid, clinician_email=$ce, patient_owner=$owner, "
            "form='T2201-PartB', fields=$f, cra_reference_number=$ref, status='attested', "
            "attested_at=time::now();",
            {"sid": screening_id, "ce": clinician_email, "owner": owner, "f": fields,
             "ref": cra_reference_number})
        rows = _rows(res)
    await write_audit(clinician_email, "attest", owner,
                      f"{clinician_email} certified T2201 Part B (ref {cra_reference_number or 'n/a'})")
    return _clean(rows[0]) if rows else {}


async def mark_attestation_submitted(clinician_email: str, attestation_id: str) -> None:
    from surrealdb import RecordID
    rid = RecordID("attestation", attestation_id.split(":", 1)[-1])
    async with _db() as db:
        await db.query(
            "UPDATE attestation SET status='submitted_in_cra', submitted_at=time::now() "
            "WHERE id=$rid AND clinician_email=$ce;", {"rid": rid, "ce": clinician_email})
        rows = _rows(await db.query(
            "SELECT patient_owner, cra_reference_number FROM attestation WHERE id=$rid;", {"rid": rid}))
    if rows:
        a = _clean(rows[0])
        await write_audit(clinician_email, "submit", a.get("patient_owner"),
                          f"Part B submitted to CRA (ref {a.get('cra_reference_number') or 'n/a'})")
