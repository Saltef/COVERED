# Covered 🍁

Helps Canadians discover and claim the **health benefits they're owed** — in one short voice
conversation that ends with ready-to-submit applications. Built for **Build North: Ship Something
Real** (Georgian).

> We **inform and prepare**; a human **confirms and submits**. Nothing is filed to government
> automatically.

See [PLAN.md](PLAN.md) for the charter, [DEMO.md](DEMO.md) for the 2-minute script,
[DEVPOST.md](DEVPOST.md) for the writeup, and [DEPLOY.md](DEPLOY.md) to ship it.

## What it does
1. **Voice interview** — answer out loud; Cohere transcribes, reads back, checks spelling; the
   profile fills live (typing works too).
2. **Screening with reasons** — a deterministic rules engine scores 7 federal/Ontario programs and
   shows the **DTC unlock chain**; the model phrases the "why" in plain language.
3. **Apply** — prepares completed applications (e.g. **T2201 Part A**), color-coding pre-filled vs.
   what you add vs. what your doctor signs, and exports a PDF.
4. **Caseworker co-pilot** — an Eon/Era-powered agent answers questions over a simulated agency's CRM.

## Architecture (modular, layered)
```
app/
  api/        FastAPI routes (screen, interview, apply, me, ops, benchmark, config)
  domain/     7 programs + rules engine + DTC unlock graph   (pure stdlib)
  eval/       ground-truth benchmark + Era adapter
  ops/        Eon ops co-pilot (tool-use agent) + its benchmark over Era data
  db/         SurrealDB repository + schema (row-level security)
  security/   Clerk authn · RBAC · row-level security
  agents/     Cohere voice (STT) · plain-language explainer
  llm.py      swappable OpenAI-compatible provider (OpenRouter)
  seed/       synthetic personas
web/          voice frontend (records 16kHz WAV, browser TTS, live form)
scripts/      run_demo · smoke_api · run_benchmark · run_ops_benchmark · test_rls · test_voice · era_probe
```
**The rules engine decides eligibility (deterministic, auditable). The model only phrases the "why".**

## Partners / stack
- **SurrealDB** — persistence + two-layer **row-level security** + the unlock graph.
- **Cohere** — Canadian speech-to-text (Transcribe).
- **Clerk** — authentication + senior/caregiver roles.
- **Eon / Era** — simulated agency; the ops co-pilot is benchmarked on Era's ground truth.
- **OpenRouter** — swappable LLM (run `anthropic/claude-3.5-haiku` for cheap Claude).
- Figures verified against **2025 CRA / Ontario** public rates.

## Security
- **Auth:** Clerk (OIDC/JWT), verified locally; no passwords stored. RBAC: senior / caregiver / admin.
- **Row-level security:** every record owner-scoped in the app *and* in SurrealDB table permissions;
  caregiver access only via an explicit least-privilege grant.
- **PII:** minimized; raw audio/documents processed then discarded; secrets gitignored; human-in-the-loop.

## Run
```bash
# offline core (no deps, no keys)
python scripts/run_demo.py

# full stack
docker compose up --build         # app :8000 · SurrealDB :8001
```
Add keys in `.env` (see `.env.example`): `OPENROUTER_API_KEY` (agents + explanations),
`COHERE_API_KEY` (voice), `CLERK_*` (auth), and the `HUBSPOT_*`/`ERA_*` set for the ops co-pilot.

## Verify
```bash
python scripts/run_benchmark.py        # screening accuracy vs ground truth  -> 100% (70/70)
python scripts/run_ops_benchmark.py    # Eon ops co-pilot vs Era ground truth -> 5/5  (needs keys)
python scripts/test_rls.py             # row-level security isolation          (needs SurrealDB up)
python scripts/test_voice.py           # Cohere transcription path             (needs COHERE_API_KEY)
python scripts/smoke_api.py            # all HTTP endpoints
```

## Status
✅ Foundation · voice interview · persistence + RLS · Clerk auth · apply/PDF · verified figures ·
screening benchmark (100%) · Eon ops co-pilot (100%) · live voice (Cohere).
⬜ Deploy + record the demo (see DEPLOY.md / DEMO.md).
