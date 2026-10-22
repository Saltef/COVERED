# Covered: prioritized fix list

From the functionality critique. Effort legend: **S** = under 2h, **M** = about half a day, **L** = a day or more.
Priorities: **P0** = do before the demo (honesty and fragility), **P1** = strengthen the core before judging,
**P2** = post-hackathon and productionization.

## P0: before the demo

### 1. Make the security posture honest  (S) — DONE
The app runs with `dev_allow_no_auth = True` and no Clerk keys, so any caller sending `X-Dev-Role: admin`
reaches the agency console, every screening (income, disability), the audit log, and the partner API. The
RLS and RBAC code is real but bypassed.
- [x] Startup now calls `Settings.assert_auth_safe()`, which refuses to boot when `dev_allow_no_auth` is on
  outside a development env (staging counts as unsafe, not just production).
- [x] The dev header-identity fallback is gated on `is_development`, not merely `not is_production`, so staging
  no longer accepts header auth.
- [x] `/config` exposes `auth_enforced`; the agency and clinician consoles show a red "Dev mode: auth off"
  badge when it is false, so the demo never misrepresents the posture.
- Still open (see #8): wiring Clerk so auth is actually enforced, not just honestly labeled.

### 2. Shrink the demo dependency surface  (S) — DONE
A clean run currently needs SurrealDB, OpenRouter, Cohere, and Era all up at once.
- [x] `scripts/preflight.py`: one command that pings all four, reports OK/WARN/FAIL with the reason,
  names which demo features degrade per dependency, prints the auth posture, and exits non-zero only
  when a required dependency (SurrealDB) is down. `--no-llm` skips the live LLM call.
- [x] Confirmed graceful degradation in code: the explainer falls back to deterministic text with no
  LLM; co-pilots return `available:false`; voice returns `available:false`; SurrealDB-down returns 503
  that the frontends swallow into an empty state. Screening itself never needs the LLM.
- Why: four external dependencies is four ways the live demo breaks; now you know before you present.

### 3. Pick the demo spine and cut what you show  (S)
Ten surfaces split the story. Decide the spine (core screen-to-apply loop plus the embed pivot) and present the
care team and agency as "where this goes."
- [x] Era CRM co-pilot demoted on the agency page; book co-pilot leads (done, see #6).
- Still a presentation call: decide the spine you actually walk judges through (core screen-to-apply loop
  plus the embed pivot) and present the rest as "where this goes."
- Why: depth on three things beats ten half-built ones.

## P1: strengthen the core

### 4. Stop implying clinician verification is real  (S now, L for real) — DONE (short term)
`verify_clinician` is a stub that approves on field presence, yet "verified doctors" is the care team's trust
premise.
- [x] The clinician page labels it honestly: a prominent demo-verification callout before, and an amber
  "Verified (demo)" badge with a "simulated check only" note after, driven by the profile's real
  `method == "stub"` so it stays accurate if a real verifier is ever added.
- Still open: a real provincial-college register lookup via the `RegistryVerifier` seam. **L**, out of scope
  for the hackathon.

### 5. Get an independent accuracy check  (M) — DONE
The engine passes 11/11, but we wrote both the rules and the answer key, so a wrong threshold passes green.
- [x] Spot-checked three thresholds against canada.ca: CDCP ($90k adjusted family net income cap, all ages
  since May 2025) confirmed; METC (lesser of $2,834 and 3% of net income at 15%) confirmed; CDB confirmed
  with a caveat — the engine uses the Jul 2026–Jun 2027 indexed figures ($204.20/mo, $23,483 single), which
  is right for the current date, though canada.ca pages disagree slightly on the forward numbers.
- [x] Every program now carries an official `source_url`; the engine exposes a `rates_verified` date
  (2026-10-21). Both the senior results and the embed widget show an "Official rules & rates" link per
  program and a "Rates verified <date>" line. Exposed in the `/screen` and `/v1/eligibility` responses.
- Why: turns "matches our belief" into "matches the law, traceable to the page."

### 6. Consolidate the agency co-pilots  (S) — DONE
Two co-pilots over different data (Era CRM vs the screened book) confuse. The book one is the real story.
- [x] The book co-pilot is primary. The Era box is recast as a "Live data ingestion" proof card (live
  connection status, record count, the honest not-screenable note, and the accuracy benchmark), with the
  open-ended CRM co-pilot tucked into a collapsed "Try the live CRM co-pilot" detail. The agency intro now
  leads with the book.

### 7. Make document auto-fill show its work  (M) — DONE
Notice-of-Assessment extraction uses LLM vision with no validation shown.
- [x] Auto-fill no longer writes to the form on its own. Extracted values appear in a confirmation panel
  with a plain warning that AI reading can be wrong; each value is editable and has a checkbox, and they
  reach the form only when the caregiver clicks "Apply to form" (or discards). Every field is reviewable,
  which is stronger than flagging only low-confidence ones.
- Why: the failure mode was silent wrong data in a benefits form; now a human confirms every value.

## P2: post-hackathon and productionization

### 8. Wire Clerk end to end  (L)
Real authentication across all roles, replacing dev-mode identity. Turns the architected RLS into enforced RLS.

### 9. Make cross-origin embedding real  (M-L)
The widget works in the demo only because host and API are same-origin; prod CORS is empty, so a real partner
domain is blocked. Needs a per-partner CORS allowlist and real partner-key issuance, not the hardcoded demo key.

### 10. Add an automated test suite  (M) — DONE
`pytest` is not installed and there is no `tests/`; what exists is three manual scripts plus the benchmark.
- [x] Added a `pytest` suite in `tests/` organized into four layers (engine matrix, API contracts, persona
  journeys, resilience) and documented in `USE-CASES.md`. 46 tests; all green with SurrealDB up, 41 pass and
  5 skip cleanly with it down, so it runs in CI with no database. The engine matrix is data-driven off
  `ground_truth.CASES`, so the benchmark now fails the build on a rules regression.
- `requirements-dev.txt` pins pytest; `pytest.ini` sets the path and test discovery.

### 11. Harden the public surface  (M)
Tighten CORS off `*`, rate-limit `/v1/eligibility`, and remove the demo-key acceptance path outside dev.

### 12. Be precise about submission tracking  (S) — DONE
"Mark submitted in CRA" is self-report with no CRA integration (correct by design). Label it as self-reported so
status is not mistaken for a live CRA signal.
- [x] Clinician: the post-submit badge now reads "Marked submitted in CRA · self-reported" with a note that
  Covered records what the clinician entered and receives no status back from CRA.
- [x] Caregiver status tracker: dropped "awaiting decision", relabeled to "Submitted in CRA (self-reported)",
  and added a one-line note that all statuses are self-reported, not fed from CRA or the programs.
- The mock tax app's own "Submitted via NETFILE" line is left as-is: it is the fictional host's claim, not
  Covered's tracking.

## What not to touch

The deterministic rules engine is the strongest asset (11/11, correct age edge cases) and the honest flagging
(illustrative values, Era-not-screenable, CRA-owns-submission) is doing real work. Keep both.
