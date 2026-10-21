# Covered — Project Charter & Build Plan
*(working name "Covered" — change anytime)*

## 🎯 Goal (north star)
**Help a low-income Canadian senior discover and claim every health benefit they're owed —
in one short voice conversation that ends with completed, ready-to-submit applications —
so the money that normally goes unclaimed actually reaches them.**

Success = one number on screen: **"$X/year you're not getting, across N programs."**

We **inform and prepare**. A human (or their caregiver) **confirms and submits**.
We never file to government automatically. (This is our Security & Ethics line.)

## Hackathon
Build North: Ship Something Real (Georgian). Build week Oct 16–25, submit **Oct 25 23:59 ET**,
online judging Oct 26, Demo Day Oct 29 (Toronto).
Judging: Innovation · Real-World Impact · UI & Design · Tech & Deployment · Security & Ethics.

## Persona & programs
Anchor persona: **low-income senior (ON)**. Programs:
DTC · Canada Disability Benefit · Canadian Dental Care Plan · Medical Expense Tax Credit ·
Canada Caregiver Credit · RDSP · Ontario Trillium Drug Program.
Spine: the **DTC "unlock chain"** (DTC → CDB / RDSP). *(CDCP is open to all ages since May 2025, so it's no longer DTC-gated.)*

## Architecture (modular, layered)
API layer (FastAPI) → Domain layer (rules engine) → Data layer (SurrealDB).
Cross-cutting: Security layer (authn/authz/RLS), Agents layer (Claude + Cohere).
**The rules engine decides eligibility (deterministic, auditable). Claude only phrases the "why."**

```
app/
  api/        HTTP routes
  domain/     programs + rules engine + unlock graph   (PURE, no I/O, stdlib-only, unit-testable)
  models.py   domain types (dataclasses)
  db/         SurrealDB connection + schema (row-level permissions)
  security/   Clerk authn, RBAC authz, row-level security
  agents/     Claude (interview/explain) + Cohere (STT) — graceful degradation without keys
  seed/       sample personas
scripts/      offline demo runner
```

## 🔒 Security standards (non-negotiable)
- **Authentication:** Clerk (OIDC/JWT). Backend verifies tokens; we store no passwords.
- **Authorization (RBAC):** roles `senior` / `caregiver` / `admin`, enforced per route.
- **Row-Level Security (RLS):** every record carries an `owner`; all data access is scoped to the
  authenticated identity. Caregiver access only via an explicit, least-privilege `access_grant`.
  Enforced in **two layers**: app data-access + SurrealDB table PERMISSIONS (defense in depth).
- **PII:** minimize collection; raw documents (e.g. Notice of Assessment images) are processed then
  **discarded** (not persisted); logs redact PII; secrets in `.env` (gitignored), never committed; TLS in prod.
- **Human-in-the-loop:** no automated government submission.
- **Audit:** record-access audit trail.

## Partners (committed)
Claude (brain) · SurrealDB (memory + unlock graph + RLS) · Cohere (voice STT) ·
Clerk (authn + caregiver role) · Eon/Era (agent benchmark & eval). *Expo dropped (solo + Python).*

## Checkpoints / milestones  (◆ = I stop and prompt you)
- ◆ **M1 — Foundation runs:** domain core + `/screen` on the seeded persona, offline, no keys ← *today*
- ◆ **M2 — Voice interview** (Cohere STT + browser TTS) → profile → screening + unlock graph
- ◆ **M3 — Persistence & auth:** SurrealDB with row-level permissions + Clerk auth live
- ◆ **M4 — Apply:** form-fill (T2201 etc.) → ready-to-submit package + caregiver role
- ◆ **M5 — Eon/Era benchmark** + dashboard ("$X/yr across N programs")
- ◆ **M6 — Demo video + deploy + Devpost**

## Timeline (~5 days)
| Day | Target |
|---|---|
| Oct 20 | M1 + Clerk skeleton + confirm Era access |
| Oct 21 | M2 |
| Oct 22 | M3 + start M4 (form-fill) |
| Oct 23 | M5 (Eon benchmark) + dashboard |
| Oct 24 | Harden demo path + record + deploy + Devpost |
| Oct 25 | QA → submit (afternoon) |

## ⚠️ Verification tasks (before demo)
- **V1** — ✅ Done (Oct 20). Figures verified against 2025 CRA / Ontario public sources; per-figure
  sources are in `app/domain/programs.py`. Individual amounts still depend on the person's situation.
- **V2** — Confirm Era by Eon early-access API / MCP access (via hackathon Discord).

## Run
- Offline core: `python scripts/run_demo.py`
- Full stack: `docker compose up`  (app on :8000, SurrealDB on :8001)
