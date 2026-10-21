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
- Set `APP_ENV=production` and `DEV_ALLOW_NO_AUTH=false` — this disables the local no-auth dev identity.
- Set real **Clerk** keys (without them, endpoints have no real auth).
- Tighten CORS (it's `*` in dev; restrict to your frontend origin).

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
- Open the site and run the voice interview end to end.
