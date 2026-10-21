# Covered — Polish & Hardening Plan

Four workstreams to make the product cohesive, correct, reliable, and fast. Each has concrete
tasks (with files) and acceptance criteria. Recommended order at the bottom.

---

## A. One cohesive "nice orange" design system
**Problem:** the four surfaces drift. `index.html` (senior) is a warm orange theme; `caregiver.html`,
`clinician.html`, `agency.html` are cool-gray "SaaS" with only an orange accent. Tokens are duplicated
in each file and the primary orange differs (`#c2410c` vs `#ea580c`).

**Tasks**
- [ ] **A1. Canonical palette.** One token set: primary `#c2410c`, accent `#ea580c`, warm bg (`#fff7f0`),
  tints, semantic ok/maybe/off, line, shadow, radius, type scale. Document + check WCAG AA.
- [ ] **A2. Shared stylesheet.** Create `web/styles.css` with the tokens + base components (buttons,
  cards, pills/badges, tables, inputs, focus rings, top bar, chips). Serve it via a static mount in
  `app/main.py`; link it from all four pages.
- [ ] **A3. Refactor pages** to the shared classes; delete per-page token/component duplication; keep
  only page-specific layout.
- [ ] **A4. Warm the professional pages** — subtle orange-tinted background + orange primary buttons/
  accents on caregiver/clinician/agency, staying clean and professional (not gray).
- [ ] **A5. Accessibility** — AA contrast, visible focus rings, 44px+ targets, works at phone width.

**Acceptance:** one CSS source of truth, one palette, consistent components; all four pages read as one
orange product; AA contrast throughout.
**Files:** new `web/styles.css`; `app/main.py`; `index.html`, `caregiver.html`, `clinician.html`, `agency.html`.

---

## B. Make every function work as intended (QA)
**Tasks**
- [ ] **B1. Green test suite.** Run and fix: `run_demo`, `smoke_api`, `run_benchmark`,
  `run_ops_benchmark`, `test_rls`, `test_voice`, `test_care_team`, plus the status/extract checks.
- [ ] **B2. Click-through each role** end to end in the browser (senior, caregiver, clinician, agency);
  log and fix bugs; confirm no console errors.
- [ ] **B3. Data hygiene.** The DB has leftover/duplicate test rows ("(unnamed)", several Margarets,
  0-program entries). Add a `scripts/reset_demo.py` (clear + seed one coherent demo set: a patient,
  a doctor, a couple of clients) so demos are clean.
- [ ] **B4. Cross-role coherence.** Verify the patient→doctor→status→audit flow with distinct identities
  (`X-Dev-User`); make the demo path (one patient, one doctor) clean and repeatable.
- [ ] **B5. States.** Consistent empty / loading / error (404/503) states everywhere.
- [ ] **B6. Degradation.** Confirm the app runs with no keys (voice/LLM/Era fall back) and with keys.

**Acceptance:** all scripts green; each flow completes without errors; clean demo data; graceful with/without keys.

---

## C. Verify functionality & benefit accuracy
**Tasks**
- [ ] **C1. Re-verify each program** against canada.ca / ontario.ca (capture sources + "last verified"):
  DTC amount & 2026 digital process; CDCP income cap/tiers/eligibility/renewal; METC threshold/rate/
  line 33099; CDB max/thresholds/ages; Trillium deductible formula; Canada Caregiver Credit; RDSP
  age/grants; the OAS/GIS note for seniors 65+.
- [ ] **C2. Reconcile the code** — `app/domain/programs.py` constants + logic, `app/eval/ground_truth.py`
  labels, and `app/domain/applications.py` copy (form names, line numbers, submission steps) with the
  verified facts; update.
- [ ] **C3. Gates & chain** — confirm the DTC unlock chain and the age/province eligibility gates match policy.
- [ ] **C4. Re-run the benchmark** (`run_benchmark.py`) — expect 100% or fix what it surfaces.
- [ ] **C5. Honesty** — inline source citations + a verified date; keep "estimate" wording where amounts
  are person-specific.

**Acceptance:** every figure traceable to a current official source; benchmark green; application copy correct.

---

## D. UX — expedite what users do now
**Tasks (prioritized by impact)**
- [ ] **D1. Senior interview** — tighten the inter-question delay; clarify "Redo"; add an end-of-interview
  "review & edit answers" step before results; smoother voice auto-advance; clearer mic states.
- [ ] **D2. New-screening form** — lead with document auto-fill; mark non-essential fields optional with
  smart defaults; Enter-to-advance; inline validation.
- [ ] **D3. Record detail** — it's a long stack (results → apply → progress → care team → activity).
  Reorganize into clear sections/tabs; surface the headline + next action first; consider auto-preparing
  applications on open.
- [ ] **D4. Navigation** — a consistent top nav across the professional pages (Caseload / Clinician /
  Agency) with a "you are here" state, replacing the scattered "↗" links.
- [ ] **D5. Fewer clicks** — sensible defaults, one-click common actions, quick status advance.
- [ ] **D6. Responsive** — verify senior + caregiver at phone width (seniors use phones).
- [ ] **D7. Feedback** — consistent toasts/spinners for async actions.

**Acceptance:** measurably fewer steps per core task; clearer flow; mobile-friendly; every async action gives feedback.

---

## Recommended order
1. **C — accuracy** (correctness is foundational and cheap to do first).
2. **B — QA** (fix what's broken; clean the demo data).
3. **A + D together** (both are frontend-heavy — unify the orange *and* streamline the flows in one pass).

Rough shape: C ≈ 1–2 passes · B ≈ 1–2 passes · A+D ≈ 2–3 passes.
