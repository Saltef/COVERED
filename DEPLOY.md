# Deploying Covered

## Must-haves
- **HTTPS.** The microphone (Web Audio / getUserMedia) only works in a secure context. Every option
  below gives TLS; `localhost` is also fine for local demos.
- **Two services:** the FastAPI app + SurrealDB.

## Secrets (set as host environment variables, never commit)
| Var | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | LLM for the ops co-pilot + explanations |
| `OPENROUTER_MODEL` | **Recommended: `anthropic/claude-3.5-haiku`** — cheap Claude, keeps the Anthropic-host story |
| `COHERE_API_KEY` | voice speech-to-text |
| `CLERK_PUBLISHABLE_KEY` / `CLERK_JWT_KEY` / `CLERK_SECRET_KEY` | auth (see hardening below) |
| `SURREAL_URL` (`ws://surrealdb:8000/rpc`), `SURREAL_USER/PASS/NS/DB` | database |
| `HUBSPOT_BASE_URL`, `HUBSPOT_MCP_HEADER`, `ERA_SYSTEM=hubspot`, `ERA_RECORDS_PATH=/crm/v3/objects/contacts` | Eon ops-co-pilot demo |

> ⚠️ The Era bearer token **expires (~weekly)**. Regenerate with `era mcp <tenant>` before the demo.

## Harden before a public deploy
Start from `.env.production.example`. In short:
- Set `APP_ENV=production` and `DEV_ALLOW_NO_AUTH=false`. The app refuses to boot if the no-auth dev
  identity is on outside development, so a misconfigured deploy fails closed instead of running open.
- Set real **Clerk** keys. Without them, every authenticated endpoint (agency, care team, saved
  screenings) returns 401. The public screeners (`/`, `/benefits`, `/homecare`, `/v1/eligibility`) work
  without auth.
- Set `ALLOWED_ORIGINS` to your exact site origin(s). In production CORS is closed to everything else.
- The `demo-partner-key` is never accepted in production; issue real keys via `PARTNER_API_KEYS`.

## Images
- The `Dockerfile` is production-ready: non-root user, a `/healthz` HEALTHCHECK, no `--reload`, and
  `WEB_CONCURRENCY` uvicorn workers. `docker-compose.yml` overrides the command with `--reload` for local dev.

## Rate limiting
- Do it at the edge (your platform, or Cloudflare) on `/v1/eligibility` and the LLM-backed co-pilot
  routes. In-process limiting is unreliable across multiple workers, so it is not built in.

## Option A — one small VM + Caddy (simplest full stack)
1. Provision a 1–2 GB VM; install Docker + Compose.
2. Copy the repo and a `.env` with the secrets above.
3. Front it with Caddy for automatic HTTPS — `Caddyfile`:
   ```
   covered.example.com {
     reverse_proxy localhost:8000
   }
   ```
4. `docker compose up -d --build`

## Option B — Railway / Render (managed, Docker)
Deploy the app from the `Dockerfile`; add SurrealDB as a second service (or use Surreal Cloud); set
the env vars in the dashboard. Both give HTTPS out of the box.

## Option C — Google Cloud Run (partner credits)
Build & push the app image; deploy to Cloud Run (HTTPS by default); point `SURREAL_URL` at a Surreal
Cloud instance; store secrets in Secret Manager.

## Post-deploy smoke check
- `GET /healthz` → `surrealdb: connected`
- `GET /benchmark` → `decision_accuracy: 1.0`
- `GET /ops/benchmark` → scores once OpenRouter + Era are set
- Open the site; the home-care journey loads, and a screening runs end to end.

## Production readiness checklist
Code-side (done in the repo): fail-closed auth gate, production Docker image, configurable CORS,
`.env.production.example`, the four-layer pytest suite + CI. Still required for real users:

- [ ] A **Clerk** project, with sign-in wired into the authenticated pages (front end).
- [ ] A **managed, backed-up SurrealDB** (Surreal Cloud or a VM volume with real backups).
- [ ] A **host** (Railway / Render / Fly / Cloud Run) with the env vars set in its secret store.
- [ ] **Edge rate limiting** on the public API.
- [ ] The **privacy work** below.

## Privacy & legal (not optional for real data)
Covered collects health and income information about Ontarians, so a real deployment is subject to
**PHIPA** (Ontario's health-information law) and **PIPEDA**. Before taking real users:

- Keep data **in Canada** (choose a Canadian region for the host and the database).
- Publish a **privacy policy** and collect **informed consent** before screening.
- Minimize and retain data only as needed; the domain model already keeps PII to a first name.
- Consider a **privacy review / PIA** before handling real records.

## What stays human (the honest ceiling)
CRA, CILT's Direct Funding, and ADP do not accept third-party API submissions. Covered screens,
prepares, hands off and tracks; the actual filing stays with the person, their clinician, or CILT.
