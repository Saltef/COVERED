# Covered 🍁

Covered helps older adults and their caregivers find and set up home care in Ontario, and prepares the real applications. Built for Build North: Ship Something Real (Georgian).

Covered informs and prepares. A person confirms and submits. Nothing is filed to government automatically.

## What it does

**Home care (the front door).** Answer a few questions and Covered routes you to the right program and your real next steps:
- **Direct Funding** (self-managed attendant services, administered by CILT): eligibility against Ontario Reg 367/94, a real monthly budget estimate from CILT's own formula, and the real application sections.
- **Ontario Health atHome** (agency-arranged care) for people who do not self-manage: the services, the process, and how to start.

**Other benefits (`/benefits`).** A deterministic screener for 7 federal and Ontario programs (DTC, CDCP, Trillium and more) with dollar estimates and official source links per program.

**Care team (behind auth).** A caregiver dashboard, clinician Part B coordination for the Disability Tax Credit, and an agency console with a co-pilot over the screened book.

## How it works

The rules engine decides eligibility. It is deterministic and auditable. A regression suite of hand-labeled cases keeps it internally consistent and catches policy drift (it passes every case, which proves no regression, not real-world correctness). The real accuracy check is separate: a policy drift checker compares each dollar figure and threshold against the official government source, so every program carries a source link and a verified date. The model only phrases the plain-language explanation.

## Run

```bash
# offline core, no keys needed
python scripts/run_demo.py

# full stack
docker compose up --build    # app on :8000, SurrealDB on :8001
```

The home-care journey needs no database or keys. The care team and the co-pilots use SurrealDB, OpenRouter and Clerk when configured (see `.env.example`).

## Test

```bash
python -m pytest    # 4 layers: engine matrix, API contracts, journeys, resilience
```

See [USE-CASES.md](USE-CASES.md) for the test matrix and [DEPLOY.md](DEPLOY.md) to ship it.

## Stack

- **FastAPI** and **SurrealDB** (row-level security in the app and in table permissions).
- **Cohere** speech-to-text (voice is an option, not required).
- **Clerk** auth (OIDC/JWT). The app fails closed: it will not boot with the no-auth dev identity outside development.
- **OpenRouter** for the LLM (swappable; `anthropic/claude-3.5-haiku` by default).
- **Eon / Era** for the agency co-pilot demo.
