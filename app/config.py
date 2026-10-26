"""Application settings. Secrets come from the environment / .env (never committed)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    # LOCAL DEV ONLY: when true, unauthenticated requests get a dev identity.
    dev_allow_no_auth: bool = True

    # Production CORS: comma-separated allowed origins (e.g. "https://covered.example.com").
    # In development CORS is open; in production only these origins are allowed.
    allowed_origins: str = ""

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # AI / voice (optional — graceful degradation when blank)
    anthropic_api_key: str = ""
    cohere_api_key: str = ""

    # Natural text-to-speech (optional). The browser's built-in speechSynthesis sounds robotic;
    # with one of these keys set, /voice/speak returns real neural audio instead. ElevenLabs is
    # preferred when both are set. OpenRouter has no audio endpoint, so OpenAI TTS needs a direct
    # OpenAI key. Without any key the frontend falls back to the browser voice.
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"   # "Rachel": warm, natural, clear
    # eleven_turbo_v2_5 is very natural and low-latency; eleven_multilingual_v2 is a touch richer.
    elevenlabs_model: str = "eleven_turbo_v2_5"
    openai_api_key: str = ""
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "shimmer"                   # warm female; others: nova, coral, alloy

    @property
    def tts_available(self) -> bool:
        return bool(self.elevenlabs_api_key or self.openai_api_key)

    # LLM provider (OpenRouter, OpenAI-compatible) — powers the ops co-pilot + explanations.
    # Set OPENROUTER_MODEL to any OpenRouter id, e.g. "openai/gpt-4o-mini" (cheap) or
    # "anthropic/claude-3.5-haiku" (cheap Claude) or "google/gemini-2.0-flash-001" (cheapest).
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"

    # Clerk (authentication)
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwt_key: str = ""  # PEM public key for local JWT verification

    # Partner embed API: comma-separated keys that may call /v1/eligibility.
    # In dev a built-in demo key is always accepted; set real keys for staging/prod.
    partner_api_keys: str = ""

    @property
    def partner_key_set(self) -> set[str]:
        return {k.strip() for k in self.partner_api_keys.split(",") if k.strip()}

    # Era by Eon (optional: pull a client population from a simulated agency to screen)
    era_system: str = ""          # e.g. "hubspot" | "salesforce" — picks <SYSTEM>_BASE_URL/_MCP_HEADER
    era_records_path: str = ""    # vendor records collection, e.g. "/crm/v3/objects/contacts"

    # SurrealDB Agent Memory (Spectron): time-aware, traceable policy-fact store (optional).
    spectron_url: str = ""
    spectron_context_id: str = ""
    spectron_api_key: str = ""

    # SurrealDB
    surreal_url: str = "ws://surrealdb:8000/rpc"
    surreal_user: str = "root"
    surreal_pass: str = "root"
    surreal_ns: str = "covered"
    surreal_db: str = "covered"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in ("development", "dev", "local")

    def assert_auth_safe(self) -> None:
        """Fail fast if the no-auth dev fallback is on outside development.

        The dev fallback mints an identity from request headers (any caller can claim admin),
        so it must never run in a deployed environment. Checked at startup. Note that staging or
        any non-development env counts as unsafe here, not just production.
        """
        if self.dev_allow_no_auth and not self.is_development:
            raise RuntimeError(
                f"DEV_ALLOW_NO_AUTH is enabled but APP_ENV={self.app_env!r} is not a development "
                "environment. Set DEV_ALLOW_NO_AUTH=false and configure Clerk before deploying.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
