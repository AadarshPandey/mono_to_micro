# backend/config.py
"""
Monolith Breaker — Application Configuration

Pydantic BaseSettings that reads all env vars from .env file.
Singleton `settings` instance is exported for use across the entire app.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — every field maps to an env var in .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Google AI ──────────────────────────────────────────────────────
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_TEMPERATURE: float = 0.2
    GEMINI_MAX_TOKENS: int = 8192

    # ── Neo4j ─────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"

    # ── ChromaDB ──────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_NAME: str = "monolith_code"

    # ── FastAPI ────────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_KEY: str = "dev-secret-change-in-prod"
    UPLOAD_DIR: str = "./data/uploads"
    OUTPUT_DIR: str = "./data/outputs"

    # ── Pipeline ───────────────────────────────────────────────────────
    DEFAULT_LANGUAGE: str = "java"
    CONFIDENCE_THRESHOLD: float = 0.65
    DYNAMIC_WEIGHT_MULTIPLIER: float = 5.0
    MAX_CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 8

    # ── LangSmith (optional) ──────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "monolith-breaker"

    # ── OTel ───────────────────────────────────────────────────────────
    OTEL_INGEST_PORT: int = 4318

    # ── Drift detection ───────────────────────────────────────────────
    DRIFT_WEBHOOK_URL: str = ""
    DRIFT_SCAN_SCHEDULE: str = "0 2 * * *"

    def ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        for d in (self.UPLOAD_DIR, self.OUTPUT_DIR, self.CHROMA_PERSIST_DIR):
            Path(d).mkdir(parents=True, exist_ok=True)


# Singleton — import this everywhere
settings = Settings()
