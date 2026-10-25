# Covered: Devpost submission

**Tagline:** Home care in Ontario, found and prepared in one clear path.

## Inspiration

Older adults and people with disabilities in Ontario struggle to find and set up home care. The programs exist, but the paths are a maze: self-managed attendant care, agency care, tax credits, drug and dental coverage, each with its own forms and front door. People miss what they qualify for, and the paperwork is hard. We wanted one clear path that finds the right program and prepares the real application, so a person just reviews and signs.

## What it does

Covered opens on a home-care journey. Answer a few questions and it routes you to the right program with your real next steps.

- **Direct Funding** (self-managed attendant services, administered by CILT). Eligibility against Ontario Reg 367/94, a real monthly budget estimate from CILT's own formula (hours, wages, employer costs, contingency), and the real application sections laid out.
- **Ontario Health atHome** (agency-arranged care) for people who do not self-manage. The services, the process, and how to start.
- **Other benefits.** A deterministic screener for 7 federal and Ontario programs (DTC, CDCP, Trillium and more), with a dollar estimate and an official source link per program.

Covered informs and prepares. A person confirms and submits. Nothing is filed to government automatically.

## How we built it

A modular FastAPI app in Docker, with a clean separation between deterministic rules and the model.

- **Rules engine.** Pure, auditable eligibility for every program. A regression suite of hand-labeled cases (130/130 program decisions) keeps it internally consistent across income caps, province gating, age bands, and the do-not-over-claim case. That proves no regression, not real-world correctness, so the accuracy check is separate (below). The Direct Funding module encodes the real Reg 367/94 criteria and CILT's budget formula.
- **Real numbers, cited, and checked.** Every dollar figure and threshold is verified against its official source (canada.ca, ontario.ca, CILT's guide), with a source link and a verified date in the UI. A policy drift checker re-reads each official page and flags any figure that has changed, so the catalogue is the actual accuracy signal, not the hand-labeled suite.
- **Time-aware policy memory (SurrealDB Agent Memory).** The drift checker's confident readings are written to Agent Memory as facts with full provenance (value, source URL, date, verbatim quote). A changed value supersedes the prior fact rather than overwriting it, so the memory is a queryable history of what each figure was and when. The app reads the current value and its source back at `/ops/policy-history`. Only public policy facts go here; no user, health, or income data (that stays in our own SurrealDB under PHIPA).
- **SurrealDB** with two-layer row-level security: every record is owner-scoped in the repository and in the database's table permissions. Caregivers get access only through an explicit grant.
- **Honest by construction.** Auth fails closed (the app will not boot with the no-auth dev identity outside development). Demo-only features are labeled as such. The home-care journey is pure computation, so it needs no database or keys to run.
- **Agency co-pilot.** An LLM tool-use agent answers questions over the screened book and over a simulated agency CRM on Era by Eon, benchmarked against exact ground truth.
- **Swappable LLM** through an OpenAI-compatible layer (OpenRouter), running Claude for cents.
- **Tested.** A four-layer pytest suite (engine matrix, API contracts, persona journeys, resilience) runs in CI.

## Challenges we ran into

- **Breadth was hiding the product.** We first built a broad benefits screener with no clear use case. We refocused on one person and one job: older adults setting up home care. The engine and care-team work carried over; the path got clear.
- **Real forms, not fake ones.** We pulled the actual Direct Funding criteria and budget formula from CILT's own guide, so the eligibility and the estimate are real, not approximations.
- **Cheap model, exact answers.** A cheap model could not aggregate hundreds of records reliably. We moved the counting and summing into exact server-side tools; the agent just picks the right one, and accuracy went to 100%.

## What we learned

Agents win when the tools do the exact work (deterministic rules, aggregation) and the model does the language. And a product for vulnerable users wins on a clear path and honesty: one route, real numbers, real next steps, and never pretending to submit what a human must.

## What's next

Add the Assistive Devices Program; wire Clerk for the professional dashboards; a Canadian-region deploy for PHIPA; a pilot with a community agency or an Independent Living Centre.

## Built with

Python, FastAPI, SurrealDB, OpenRouter (Claude), Cohere, Clerk, Eon / Era, Docker, pytest.

## Links

- Live demo: (deployed URL)
- Repo: https://github.com/Saltef/COVERED
- Demo video: (2-min, script in DEMO.md)
