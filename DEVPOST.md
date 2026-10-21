# Covered — Devpost submission

**Tagline:** The benefits you're owed, found and prepared in one voice conversation.

---

## Inspiration
Every year billions of dollars in Canadian health and disability benefits go unclaimed. The cause
isn't fraud or scarcity — it's complexity. One in ten eligible seniors miss the Guaranteed Income
Supplement; only ~44% of likely-eligible people claimed the Canada Housing Benefit top-up. People
don't know what they qualify for, and the forms are impossible — especially for seniors, newcomers,
and people with disabilities. We wanted to close that gap: not another tax app, but an agent that
*finds* the money and *prepares* the paperwork, so a human just reviews and signs.

## What it does
Covered interviews a person **by voice**, screens them across seven federal and Ontario programs,
and prepares **ready-to-submit applications** — pre-filling everything it safely can.

- **Voice-first interview.** You answer out loud; Covered transcribes (Cohere), reads your answer
  back, checks the spelling of your name, and fills the form. Typing works as a fallback.
- **Screening with a reason.** A deterministic rules engine decides eligibility (auditable), and
  the model phrases *why* in grade-6 plain language. It surfaces the **DTC "unlock chain"** — the
  Disability Tax Credit is a key that opens the Canada Disability Benefit and the RDSP.
- **One number.** "You could be owed about **$3,736 a year** across 4 programs you may not be getting."
- **Apply, not just advise.** For each program it builds a completed application (e.g. **Form T2201
  Part A**), color-coding what's pre-filled, what you must add (SIN, address), and what your doctor
  signs — then exports a PDF. We do everything short of the signature.
- **We inform; you submit.** Nothing is ever filed to government automatically — our Security &
  Ethics line, built into the design.

## How we built it
A modular, layered FastAPI app (Python), all in Docker.

- **Domain layer** — 7 programs + rules engine + the DTC unlock graph. Pure, auditable, and
  **benchmarked at 100% (70/70 decisions) against hand-labeled ground truth** covering income caps,
  province gating, age limits, and the "don't over-claim" case.
- **SurrealDB** — persistence with **two-layer row-level security**: every record is owner-scoped in
  the repository *and* in the database's table permissions. Caregivers get access only via an
  explicit least-privilege grant. (Proven with an isolation test.)
- **Cohere Transcribe** — Canadian speech-to-text; the browser records 16 kHz WAV so it's accepted
  directly.
- **Clerk** — authentication with a senior/caregiver role model.
- **Eon / Era** — we generated a simulated healthcare agency on Era by Eon and built an **ops
  co-pilot**: an LLM tool-use agent that answers questions over the agency's live CRM and is
  **benchmarked at 100% (5/5) against ground truth computed from Era's own data** (532 contacts,
  619 companies, $976,520 in deals). This is the real-world caseworker view.
- **Swappable LLM provider** — the agents run through an OpenAI-compatible layer (OpenRouter), so the
  model is one env var. We run Claude (via `anthropic/claude-3.5-haiku`) for cents.
- **Figures verified** — every dollar value uses 2025 CRA / Ontario public rates, cited in the code.

## Challenges we ran into
- **Era is enterprise-shaped.** Era by Eon generates B2B CRM/estate data with *enterprise* ground
  truth — it has no benefit-eligibility fields. Rather than fake it, we used Era for what it's great
  at: benchmarking a tool-use agent (the caseworker co-pilot) against exact ground truth, and kept
  screening accuracy on our own labeled set.
- **Cheap model, exact answers.** A cheap model couldn't aggregate hundreds of raw CRM values in its
  head (20% on the first run). We moved the counting/summing into the tools (exact, server-side) — the
  agent just picks the right tool, and the score jumped to 100%.
- **Browser audio vs Cohere.** Browsers record WebM, which Cohere rejects. We encode 16 kHz mono WAV
  client-side (Web Audio) so no server transcoding is needed and the mic works anywhere over HTTPS.

## Accomplishments we're proud of
- A benefits agent that **prepares real applications**, not just advice.
- **100% on both benchmarks** — screening accuracy and the Eon ops co-pilot.
- Honest, defensible engineering: deterministic eligibility, verified figures, row-level security,
  and a human-in-the-loop guardrail we never cross.

## What we learned
Agents win when the tools do what tools are good at (exact aggregation, deterministic rules) and the
model does what it's good at (language, orchestration). And for vulnerable users, *accessibility and
trust* — voice, plain language, "you decide" — are the product, not features.

## What's next
Multilingual voice; more provinces; a caseworker console on the Eon integration; real DTC form
(Part A) PDF pre-fill against the CRA template; pilot with a community agency.

## Built with
Python · FastAPI · SurrealDB · Cohere (Transcribe) · Clerk · Eon / Era · OpenRouter (Claude
`claude-3.5-haiku`) · Docker · Web Audio API · reportlab · PyJWT

## Links
- Live demo: *(deployed URL — see DEPLOY.md)*
- Repo: *(GitHub URL)*
- Demo video: *(2-min, script in DEMO.md)*
