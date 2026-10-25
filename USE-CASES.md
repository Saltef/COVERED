# Covered: test use cases

How the platform's many features are tested without a bespoke test per endpoint. Cases are
organized into four layers by cost and reliability, and each layer is data-driven where it can be,
so adding a case is adding a row, not writing new plumbing.

## Run it

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

With SurrealDB up (`docker compose up -d surrealdb`, host port 8001), every layer runs. Without it,
the database-dependent cases skip and the rest still run, so the suite is safe in CI with no DB.
Current status: 46 tests, all green with the DB up; 41 pass and 5 skip with the DB down.

The live-dependency smoke check (`python scripts/preflight.py`) is complementary: it tells you
whether the real SurrealDB / OpenRouter / Cohere / Era are reachable before a demo. The pytest suite
proves behaviour; preflight proves connectivity.

## Layer 1, rules engine matrix  (`tests/test_engine.py`, no dependencies)

The core correctness layer: fast, deterministic, needs nothing external. The canonical table is
`app/eval/ground_truth.py` (`CASES`), each row a `{profile, expected_actionable}`. The parametrized
test runs every row; the targeted tests pin one branch each so a failure names the broken rule.

| Case | Asserts |
|---|---|
| Every `ground_truth` case (11) | the actionable program set matches the hand-labelled answer key |
| Benchmark is perfect | `run()` reports 11/11 cases, 100% of decisions |
| Every program is evaluated | all 7 programs return a result for any profile |
| CDB excluded at 65+ | seniors use the OAS/GIS stream, not CDB |
| CDB included at working age with DTC | 18–64 with a DTC certificate is actionable |
| RDSP excluded at 60+ | an RDSP must be opened before 60 |
| CDCP open to all ages without DTC | the May 2025 expansion, no age/DTC gate |
| CDCP excluded when insured / over the $90k cap | the two disqualifiers |
| Trillium only in Ontario | province gate |
| DTC certificate is high confidence | holding the certificate is near-certain |

To add an engine case: append a row to `ground_truth.CASES`.

## Layer 2, API contracts  (`tests/test_api_contracts.py`, TestClient; DB-free unless noted)

One test per endpoint for response shape plus the honesty guarantees. No browser, no running server.

| Case | Asserts |
|---|---|
| `/healthz`, `/config` | ok status; `/config` reports `auth_enforced:false`, `dev_mode:true` in dev |
| `/screen` contract | headline, `rates_verified`, a `source_url` on every program, summary keys |
| `/screen` role gate | a clinician identity is 403 (senior/caregiver only) |
| `/v1/eligibility` auth | missing or wrong `X-Covered-Key` is 401 |
| `/v1/eligibility` contract | api_version, CAD, `rates_verified`, disclaimer, programs sorted claimable-first, `source_url` each |
| `/benchmark` endpoint | cases_passed == n_cases |
| Pages served (7) | `/`, `/caregiver`, `/clinician`, `/agency`, `/pharmacy`, `/tax`, `/developers` return HTML |
| Auth gate fails closed | `assert_auth_safe()` raises for staging and production, not development |
| `/agency/book-stats` admin only *(DB)* | senior is 403; admin is 200 with the rollup shape |

## Layer 3, persona journeys  (`tests/test_journeys.py`, require SurrealDB)

Each test walks one persona through several features end to end, which is where integration bugs
show. Writes use random dev-user ids so runs never collide.

| Journey | Features exercised |
|---|---|
| Senior applies | `/apply` builds packages, `/apply/{id}/pdf` returns a real PDF |
| RLS isolation | patient A's screening is invisible to patient B (list and direct fetch) |
| Care-team Part B loop | create screening → invite clinician → verify → pending queue → attest Part B |
| Agency book rollup | seed screenings under a caseworker → admin `/agency/book-stats` aggregates them |

## Layer 4, resilience  (`tests/test_resilience.py`, no live deps needed)

Each test removes one dependency and asserts the surface degrades instead of crashing. These mirror
`scripts/preflight.py`.

| Case | Asserts |
|---|---|
| Screening without the LLM | `/screen` still 200; explanation falls back to deterministic text |
| Explainer without the LLM | returns the fallback summary, no exception |
| Book co-pilot without the LLM | `/ops/ask-book` returns `available:false` |
| Voice without Cohere | `transcribe()` returns `available:false` |
| Storage down | a `SurrealUnavailable` surfaces as a 503, not a crash |

## What is deliberately not here

- Live transcription accuracy (needs real speech), covered by `scripts/test_voice.py` and the browser mic.
- Live LLM answer quality for the co-pilots, covered by `/ops/benchmark` against ground truth.
- Real clinician-register verification and real CRA submission, not built (see FIXES.md #4, #12).
- Cross-origin embedding on a third-party domain, not solved for production (FIXES.md #9).
