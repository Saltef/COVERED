# Covered, Patient-Centric Care-Team Platform (Design Spec)

Status: **design, pre-build** · Supersedes the role notes in the charter for the care-team work.

## 1. Vision & principles
Covered becomes the **patient's portable care-coordination hub**. The patient owns their record and
invites their own care team; the team travels *with* the patient across clinics, agencies, and years
,  the opposite of records trapped inside each provider's system.

Principles:
- **Patient-owned.** The patient is the root of the access graph. They grant and revoke access.
- **Portable.** The team and history belong to the patient, not an institution.
- **Minimum necessary.** Each member sees only what their role needs.
- **Verified trust.** Only a verified clinician can sign medical attestations.
- **Human-in-the-loop.** Covered prepares and coordinates; the clinician attests and submits Part B
  **in CRA's own portal**; the patient submits their applications. Covered files nothing to government.

## 2. Roles
| Role | Who | Default scope | Can |
|---|---|---|---|
| **patient** | the person / client (owner) |, (owns record) | manage own record, invite/revoke team, submit |
| **caregiver** | family member | `read` + `screen` | view, run screenings, prepare applications |
| **support_worker** | PSW, community navigator | `read` + `screen` (agency-linked) | caseload of patients, same as caregiver at scale |
| **clinician** | physician / nurse practitioner | `medical` (must be **verified**) | view minimum-necessary info, complete & attest medical forms (T2201 Part B) |
| **admin / agency** | agency oversight | org-scoped | caseload oversight + the Eon/Era ops co-pilot |

A person can hold different roles for different patients (a nurse is a clinician for her patients and
a caregiver for her own parent).

## 3. Access model (scopes)
Access is a **grant from the patient** to a member, carrying a **role** and a **scope**:
- `read`, view the screening/results.
- `screen`, run/update screenings, prepare applications.
- `medical`, complete & attest medical sections (gated to verified clinicians).

Grants are **revocable** by the patient at any time and **audited** on every access. The patient
always has full control of their own record; `admin` sees an org caseload; everyone else sees only
patients who granted them access, limited to their scope.

## 4. Data model
Builds on the existing `access_grant` + row-level-security schema.

```
patient            := the owner user (Clerk sub / dev id)
screening          := { id, owner(patient), name, profile, results, summary, created_at }     # exists

care_team_grant    := { id, patient, member_email, member_id?, role, scope[],
                        status: invited|active|revoked, created_at, accepted_at?, revoked_at? }
clinician_profile  := { member_id, full_name, license_number, college, province,
                        status: pending|verified|rejected, verified_at?, method }
attestation        := { id, screening, clinician, form: "T2201-PartB", fields, statement,
                        cra_reference_number?, attested_at,
                        status: drafted|attested|submitted_in_cra }    # immutable once attested
audit_log          := { actor, action, subject, at }                   # exists
```

**RLS (two layers, as today):** a screening row is visible to its `owner` (patient), an `admin`, or a
member with an **active** grant whose scope permits the action. SurrealDB table permissions mirror the
app-layer rule. Clinicians additionally get **minimum-necessary** field projection (only what Part B
needs), not the full financial profile.

## 5. Verified clinicians (the trust layer)
A random person must never be able to claim to be a doctor and sign a T2201.

Flow:
1. Clinician submits **full name + license number + provincial college** (CPSO Ontario, CPSA Alberta, …).
2. `clinician_profile.status = pending` → a **verifier** runs → `verified` / `rejected`.
3. Only a `verified` clinician with `medical` scope on a patient can create an attestation.

Verifier is **pluggable**:
- `StubVerifier`, approves for the demo (clearly labelled).
- `RegistryVerifier`, real provincial-college register lookup. **Honest caveat:** colleges publish
  public registers but mostly as web lookups, not clean APIs, so this is the documented integration
  point, not built for the hackathon. The **gate** (only verified clinicians sign) is real regardless.

Attestations are **signed, immutable, and audited**.

## 6. Core workflows
**Invite a team member**, patient enters email + role + scope → `care_team_grant(status=invited)` →
invitee opens the link and accepts → `status=active`, `member_id` bound.

**Revoke**, patient flips a grant to `revoked`; access stops immediately (app + DB layer).

**Clinician verification**, see §5.

**Clinician completes T2201 Part B** (the hero loop). **Important:** CRA owns the Part B submission , 
the doctor submits it in **CRA's own portal** using the applicant's **reference number**, and CRA
exposes no third-party API. Covered therefore **coordinates, pre-fills, hands off the reference number,
and tracks status**, it never submits Part B to CRA.
> Patient (or caregiver) completes **Part A** in CRA My Account and gets a **reference number**, entered
> in Covered → Patient → **My care team** → invite Dr. Lee → Dr. Lee **verifies** license (✓) → gets
> `medical` scope → **Pending sign-offs** shows this patient with the reference number and Covered's
> **pre-filled Part B context** (impairment details from the interview) → Dr. Lee reviews it, then
> **completes & submits Part B in CRA's portal** using the reference number → marks it done in Covered
> → the application status moves to **Part B submitted to CRA · awaiting decision.**

**Screen & prepare**, patient or caregiver/support_worker runs the screening and prepares
applications (existing engine); Part B stays "pending clinician" until a verified clinician signs.

## 7. Permissions matrix
| Action | patient | caregiver | support_worker | clinician (verified) | admin |
|---|---|---|---|---|---|
| View own/granted screening | ✓ (own) | ✓ (granted) | ✓ (granted) | ✓ (minimum necessary) | ✓ (org) |
| Run screening / prepare apps | ✓ | ✓ | ✓ |, | ✓ |
| Manage care team (invite/revoke) | ✓ |, |, |, |, |
| Attest Part B & mark submitted (doctor submits in CRA) |, |, |, | ✓ |, |
| Submit to government | ✓ (self) | with consent | with consent |, |, |
| Ops co-pilot over caseload |, |, |, |, | ✓ |

## 8. API surface (new / changed)
```
# patient, team management
POST   /me/care-team/invite      { email, role, scope[] }      -> grant
GET    /me/care-team                                           -> [grants + member status/badge]
POST   /me/care-team/{id}/revoke
POST   /care-team/accept         { token }                     -> binds member_id, status=active

# membership (a member's view)
GET    /me/memberships                                         -> patients who invited me (by role)

# clinician
POST   /clinician/verify         { full_name, license, college, province } -> status
GET    /clinician/me                                           -> verification status
GET    /clinician/pending                                      -> patients needing Part B
POST   /attestations             { screening_id, form, fields, cra_reference_number? }
                                  # requires verified clinician + medical scope; records the pre-filled
                                  # Part B + attestation. Does NOT submit to CRA (no CRA API).
POST   /attestations/{id}/mark-submitted   # doctor confirms they submitted Part B in CRA's portal

# existing, extended
GET    /me/screenings/{id}        -> now includes attestation status
```

## 9. UI surfaces
- **Patient, "My care team":** invite (email + role), list members with role + verification badge,
  revoke. Shown on the senior view (simple) and the caregiver view (professional).
- **Clinician:** verification onboarding → **"Pending sign-offs"** list (with each patient's CRA
  reference number + pre-filled Part B context) → review/attest → "submit in CRA's portal" handoff →
  mark submitted. Professional, minimal, clinical.
- **Caregiver / support worker:** the existing professional dashboard, now a *team-member* view scoped
  by grant (plus agency caseload for support workers).

## 10. Security, privacy & compliance
- **PHI/PII minimum necessary:** clinicians get a projected view (Part B needs), not full financials.
- **Consent & control:** access exists only via an explicit, revocable patient grant; every access is
  audited (`audit_log`).
- **Canadian health privacy (PHIPA / PIPEDA):** design for consent, purpose limitation, audit,
  retention and breach response. *(Not legal advice, flagged for a real deployment.)*
- **Anti-impersonation:** the verified-clinician gate; signed, immutable attestations.
- **No government submission by Covered:** CRA owns Part B submission (the doctor submits it in CRA's
  portal via the applicant's reference number; CRA has no third-party API). Covered coordinates,
  pre-fills, and tracks status only.
- **Defense in depth:** two-layer RLS (app + SurrealDB), secrets gitignored, no auto-submission.

## 11. Build phases
- **Phase 0, foundation:** extend `Role` (patient, support_worker, clinician); add `role` + `scope` +
  `status` to grants; make screenings patient-owned.
- **Phase 1, the demoable slice:** patient "My care team" + invite a doctor + **clinician verification
  (stub)** + **clinician completes T2201 Part B** + status flip to "ready to submit." ← build first.
- **Phase 2, scale:** support-worker caseloads; agency/org model wired to the **Eon/Era ops co-pilot**.
- **Phase 3, production:** real college-register verification; email invites / e-signature;
  notifications; audit UI.

## 12. Maps to existing code
| Need | Exists | Change |
|---|---|---|
| Grants | `app/db/schema.surql` `access_grant`, repo `grant_access` | add role/scope/status + patient-as-grantor |
| RLS | `app/security/rls.py` + repo scoping | add scope checks + minimum-necessary projection |
| Roles | `Role` enum (senior/caregiver/admin) | add `patient`, `support_worker`, `clinician` |
| T2201 Part B | `app/domain/applications.py` (flagged "Doctor completes") | add Part B pre-fill + `attestation` (CRA reference number + submission tracking; no CRA API) |
| Dashboards | `web/caregiver.html` | add "My care team" + clinician views |
| Audit | `audit_log` | record grants, accesses, attestations |

## 13. Open questions / risks
- **Invitee identity:** Clerk invitations vs. email magic-links for accepting a grant.
- **Real verification source:** provincial college APIs are limited; may need a manual/again-later path.
- **Minimum-necessary granularity:** how finely to project the clinician's view.
- **Jurisdiction:** PHIPA (ON) vs other provinces; scope of a real compliance review.
- **E-signature legal weight** of the attestation for CRA purposes.
