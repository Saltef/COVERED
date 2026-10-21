"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.apply import router as apply_router
from app.api.interview import router as interview_router
from app.api.me import router as me_router
from app.api.routes import router
from app.config import get_settings
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure DB tables exist; never block startup if SurrealDB is down.
    try:
        from app.db.repository import init_schema
        await init_schema()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).info("Schema init skipped: %s", type(exc).__name__)
    yield


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Covered", version="0.1.0", lifespan=lifespan,
                  description="Helps Canadians discover and claim the health benefits they're owed.")
    # Dev-friendly CORS; tighten to the real frontend origin before production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(interview_router)
    app.include_router(apply_router)
    app.include_router(me_router)
    return app


app = create_app()
