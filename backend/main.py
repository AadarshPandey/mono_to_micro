# backend/main.py
"""
Monolith Breaker — FastAPI Application Factory

Creates the app, mounts routers, registers middleware, manages lifespan.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.middleware import (
    ApiKeyMiddleware,
    GeminiKeyMiddleware,
    LoggingMiddleware,
    RequestIdMiddleware,
    TimingMiddleware,
)
from backend.api.routes import drift, jobs, output, review, upload
from backend.config import settings
from backend.db import neo4j_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup
    settings.ensure_dirs()
    logger.info("Monolith Breaker starting — API on %s:%d", settings.API_HOST, settings.API_PORT)
    try:
        await neo4j_client.get_driver()
        await neo4j_client.run_migrations()
        logger.info("Neo4j connected and migrations applied")
    except Exception as exc:
        logger.warning("Neo4j not available at startup: %s (will retry on first use)", exc)

    yield

    # Shutdown
    await neo4j_client.close()
    logger.info("Monolith Breaker shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Monolith Breaker",
        description="AI-powered monolith-to-microservice decomposition platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for Streamlit frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (order matters — outermost first)
    app.add_middleware(GeminiKeyMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIdMiddleware)
    # Uncomment for production:
    # app.add_middleware(ApiKeyMiddleware)

    # Mount routers
    app.include_router(upload.router, tags=["Upload"])
    app.include_router(jobs.router, tags=["Jobs"])
    app.include_router(review.router, tags=["Review"])
    app.include_router(output.router, tags=["Output"])
    app.include_router(drift.router, tags=["Drift"])

    @app.get("/health", tags=["Health"])
    async def health() -> dict:
        return {"status": "ok", "service": "monolith-breaker"}

    return app


app = create_app()
