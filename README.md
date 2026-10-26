![covered](brand/covered-wordmark.png)

**Home care and benefits for older adults in Ontario.** Covered helps older adults and their caregivers find the home care and benefits they qualify for, and prepares the applications. Built for Build North: Ship Something Real (Georgian).

Covered informs and prepares. A person confirms and submits. Nothing is filed to government automatically.

## See it

- **Demo video:** [demo/covered-demo.mp4](demo/covered-demo.mp4) (2:25, captioned, recorded on the running app). Screenshots in [demo/gallery](demo/gallery).
- **In the app:** `/` is a guided start page with a before/after and an Integration section that links to a working test for each piece. `/report` is the before/after report with a worked example.

## What it does

- **Home care.** Routes to **Direct Funding** (self-managed attendants, administered by CILT: eligibility against Ontario Reg 367/94 and a monthly budget estimate from CILT's published formula) or **Ontario Health atHome** (care arranged for you), with the next steps.
- **Benefits.** A deterministic screener for 10 federal and Ontario programs (DTC, CDB, CDCP, METC, CCC, RDSP, Trillium, ODB, OHIP+, ADP), each with its official source. Only amounts it can calculate are shown; coverage programs are labelled as coverage.
- **Built for busy people.** Upload a photo of a CRA Notice of Assessment to skip the income questions (the SIN is never read or stored). Tap Yes/No, type, or speak. Optional natural voice.
- **Care team.** Caregiver access by consent, clinician completion of the DTC medical part, and an agency console with a co-pilot over the caseload.
- **Integration.** An embeddable widget and a `/v1/eligibility` API for partner sites (pharmacy and tax software demos included).

## How it works

A deterministic rules engine decides eligibility; the model only writes the plain-language explanation. A regression suite of hand-labelled cases keeps the engine consistent (it proves no regression, not real-world correctness). The accuracy check is separate: a policy drift checker re-reads canada.ca and ontario.ca, has a second agent verify each figure, and flags changes for a human. Today 11 of 15 figures are checked automatically.

## Run

```bash
# offline core, no keys needed
python scripts/run_demo.py

# full stack in Docker: app on :8000, SurrealDB on :8001
docker compose up --build
```

No database server? Set `SURREAL_URL=surrealkv://data/covered.db` (persistent) or `mem://` (resets on restart) to run SurrealDB embedded in the app, single process. Keys are optional (see `.env.example` and `.env.production.example`); without them the app falls back to deterministic text and the browser voice.

## Test

```bash
python -m pytest    # 99 tests: engine, API contracts, journeys, privacy and row-level security
```

See [USE-CASES.md](USE-CASES.md) for the test matrix, [GROUNDED-USE-CASES.md](GROUNDED-USE-CASES.md) for the research behind the use cases, and [DEPLOY.md](DEPLOY.md) to ship it.

## Stack

- **FastAPI** and **SurrealDB** (row-level security in the app and in table permissions; embedded mode for single-process deploys).
- **OpenRouter** for the LLM (swappable; `openai/gpt-4o-mini` by default), which also reads the Notice of Assessment.
- **Cohere** for the policy drift checker and speech-to-text; **ElevenLabs** for the optional natural voice.
- **SurrealDB Agent Memory** for the history of policy figures (public policy facts only).
- **Clerk** auth (OIDC/JWT). The app fails closed: it will not boot with the no-auth dev identity outside development.
- **Eon / Era** for the agency CRM demo (synthetic records).
