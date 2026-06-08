# backend/api/middleware.py
"""
API Middleware — Request ID, timing, logging, and API key auth.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.config import settings

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique X-Request-ID header to every request/response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Add X-Response-Time header (milliseconds)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code, and response time."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %d (%.1fms)",
            request.method, request.url.path, response.status_code, elapsed_ms,
        )
        return response


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key header on all routes except docs."""

    EXEMPT_PATHS = {"/docs", "/openapi.json", "/redoc", "/health"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if api_key != settings.API_KEY:
            from starlette.responses import JSONResponse
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)

        return await call_next(request)


class GeminiKeyMiddleware(BaseHTTPMiddleware):
    """
    Read X-Gemini-API-Key and X-Gemini-Model headers to override settings
    for the duration of the request. This allows the frontend to pass
    the key and model at runtime without storing them in .env.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        gemini_key = request.headers.get("X-Gemini-API-Key", "")
        gemini_model = request.headers.get("X-Gemini-Model", "")

        if gemini_key:
            settings.GOOGLE_API_KEY = gemini_key
        if gemini_model:
            old_model = settings.GEMINI_MODEL
            settings.GEMINI_MODEL = gemini_model
            # Clear cached LLM if model changed so it gets re-created
            if old_model != gemini_model:
                from backend.ai.llm_client import clear_cache
                clear_cache()
                logger.info("Gemini model changed: %s → %s", old_model, gemini_model)

        return await call_next(request)

