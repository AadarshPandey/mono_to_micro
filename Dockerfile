# Dockerfile
# ── Monolith Breaker — Dockerfile ──────────────────────────────────────────
# Multi-stage build using uv for fast dependency installation.
# Runs both FastAPI backend (port 8000) and Streamlit frontend (port 8501).

# ── Stage 1: Install dependencies ─────────────────────────────────────────
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock* ./

# Install production dependencies only (no dev group)
RUN uv sync --no-dev --frozen --no-install-project 2>/dev/null || \
    uv sync --no-dev --no-install-project

# ── Stage 2: Runtime image ────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# System deps for tree-sitter C extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed venv from builder
COPY --from=builder /app/.venv /app/.venv

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY infra/ ./infra/
COPY scripts/ ./scripts/
COPY main.py ./
COPY .env.example ./.env.example

# Create data directories
RUN mkdir -p data/uploads data/outputs data/chroma

# Create .env from example if not mounted
RUN cp .env.example .env

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports: FastAPI (8000), Streamlit (8501)
EXPOSE 8000 8501

# Health check against the FastAPI backend
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["all"]
