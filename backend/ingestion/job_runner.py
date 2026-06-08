# backend/ingestion/job_runner.py
"""
Job Runner — Sequences ingestion pipeline steps and tracks job status.

Maintains an in-memory job store and orchestrates the parse → graph → embed
pipeline, then hands off to the AI orchestrator. Used by routes/upload.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from backend.api.schemas import JobResponse, JobStatus
from backend.config import settings
from backend.ingestion.ast_parser import extract_static_edges, parse_directory
from backend.ingestion.dynamic_analyzer import parse_otel_traces
from backend.ingestion.embedder import embed_and_store, update_community_ids
from backend.ingestion.graph_builder import build_graph

logger = logging.getLogger(__name__)

# ── In-memory job store ────────────────────────────────────────────────────

JOB_STORE: dict[str, JobResponse] = {}


def create_job() -> str:
    """Create a new job entry and return its ID."""
    job_id = str(uuid.uuid4())
    JOB_STORE[job_id] = JobResponse(job_id=job_id, status=JobStatus.QUEUED, progress=0, current_step="Queued")
    return job_id


def get_job_status(job_id: str) -> JobResponse | None:
    """Get current job status. Returns None if not found."""
    return JOB_STORE.get(job_id)


def update_job_status(
    job_id: str,
    status: JobStatus,
    progress: int,
    step: str,
    error: str | None = None,
) -> None:
    """Update job status in the store."""
    if job_id in JOB_STORE:
        job = JOB_STORE[job_id]
        JOB_STORE[job_id] = JobResponse(
            job_id=job_id,
            status=status,
            progress=progress,
            current_step=step,
            error=error,
        )


# ── Main job execution ─────────────────────────────────────────────────────


async def run_job(
    job_id: str,
    source_path: str,
    otel_path: str | None,
    language: str | None,
    hint_services: int | None = None,
) -> None:
    """
    Run the full ingestion pipeline for a job.

    Steps:
    1. Parse AST (Tree-sitter)
    2. Analyse dynamic traces (OTel)
    3. Build Neo4j graph + Louvain clustering
    4. Embed code into ChromaDB
    5. Hand off to AI orchestrator
    """
    lang = language or settings.DEFAULT_LANGUAGE

    try:
        # ── Step 1: Parse AST ──────────────────────────────────────────
        update_job_status(job_id, JobStatus.PARSING, 10, "Parsing source code with Tree-sitter...")
        ast_results = parse_directory(source_path, lang)
        static_edges = extract_static_edges(ast_results)
        logger.info("Job %s: parsed %d files, %d static edges", job_id, len(ast_results), len(static_edges))

        # ── Step 2: Dynamic analysis ───────────────────────────────────
        update_job_status(job_id, JobStatus.PARSING, 20, "Analysing runtime traces...")
        dynamic_edges = parse_otel_traces(otel_path)
        logger.info("Job %s: %d dynamic edges", job_id, len(dynamic_edges))

        # ── Step 3: Build graph ────────────────────────────────────────
        update_job_status(job_id, JobStatus.GRAPHING, 35, "Building Neo4j knowledge graph...")
        communities = await build_graph(ast_results, static_edges, dynamic_edges, job_id, lang)
        logger.info("Job %s: %d communities detected", job_id, len(communities))

        # ── Step 4: Embed code ─────────────────────────────────────────
        update_job_status(job_id, JobStatus.EMBEDDING, 50, "Embedding code into ChromaDB...")
        num_chunks = embed_and_store(ast_results, source_path, job_id)
        update_community_ids(job_id, communities)
        logger.info("Job %s: embedded %d chunks", job_id, num_chunks)

        # ── Step 5: Hand off to AI orchestrator ────────────────────────
        update_job_status(job_id, JobStatus.AI_PROCESSING, 55, "Starting AI boundary detection...")

        # Import here to avoid circular dependency
        from backend.ai.orchestrator import run_pipeline

        await run_pipeline(
            job_id=job_id,
            source_path=source_path,
            otel_path=otel_path,
            language=lang,
            hint_services=hint_services,
            ast_results=ast_results,
            static_edges=static_edges,
            dynamic_edges=dynamic_edges,
            communities=communities,
        )

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        update_job_status(job_id, JobStatus.ERROR, 0, "Pipeline failed", error=str(exc))
