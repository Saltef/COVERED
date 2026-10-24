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

## Public-only deploy (no auth provider)
The fastest live product: deploy the home-care journey with no auth at all.
- Set `APP_ENV=production`, `DEV_ALLOW_NO_AUTH=false`, and `ALLOWED_ORIGINS` to your site URL. No Clerk.
- **No database or API keys needed.** The home-care screening (Direct Funding + Ontario Health atHome)
  is pure, deterministic computation, so it needs no SurrealDB and no LLM. Leave those vars blank; the
  app boots and `/healthz` simply reports the DB as not connected, which is fine here.
- **Works:** the home-care front door (`/`, `/homecare`). Add `PARTNER_API_KEYS` if you also want the
  embed/partner API live.
- **Off:** the caregiver, clinician and agency dashboards, saved screenings, and the `/benefits`
  screener all return 401. `/config` reports `pro_features: false`, and the front door hides the links
  to those pages, so there are no dead ends.
- Add an auth provider and a database later (see below) to turn the professional side on.

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

## Option B — Render (Blueprint, recommended)
A `render.yaml` Blueprint is in the repo. Steps:
1. Create a **Surreal Cloud** instance; note its `wss://` URL, user and pass.
2. Create a **Clerk** project; note the publishable key, secret key and JWT public key.
3. In Render: **New > Blueprint**, select this repo. It creates the Docker web service with HTTPS.
4. In the service's **Environment**, fill the `sync: false` secrets: `ALLOWED_ORIGINS` (your Render
   URL), the three Clerk keys, `SURREAL_URL`/`SURREAL_USER`/`SURREAL_PASS`, `OPENROUTER_API_KEY`,
   `COHERE_API_KEY`, and any `PARTNER_API_KEYS`.
5. Deploy. The app binds Render's `$PORT`; the health check hits `/healthz`.

> Render has no Canadian region (`render.yaml` uses `ohio`). Fine for a pilot with synthetic data;
> for real patient data, host in a Canadian region (see Privacy below).

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
