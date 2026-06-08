# scripts/seed_neo4j.py
"""
Seed Neo4j — Loads fixture monolith data into Neo4j for development.

Usage: python scripts/seed_neo4j.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.db import neo4j_client
from backend.ingestion.ast_parser import extract_static_edges, parse_directory
from backend.ingestion.dynamic_analyzer import parse_otel_traces
from backend.ingestion.embedder import embed_and_store, update_community_ids
from backend.ingestion.graph_builder import build_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FIXTURE_DIR = Path(__file__).parent.parent / "backend" / "tests" / "fixtures"
SAMPLE_MONOLITH = FIXTURE_DIR / "sample_monolith"
SAMPLE_OTEL = FIXTURE_DIR / "sample_otel_export.json"
SEED_JOB_ID = "seed-dev-000"


async def main() -> None:
    """Seed Neo4j with fixture data."""
    logger.info("=== Seeding Neo4j ===")

    # Connect and run migrations
    await neo4j_client.get_driver()
    await neo4j_client.run_migrations()

    # Check if fixture exists
    if not SAMPLE_MONOLITH.exists():
        logger.error("Sample monolith not found at %s — create fixture files first", SAMPLE_MONOLITH)
        logger.info("Seeding with empty graph for now...")
        await neo4j_client.close()
        return

    # Parse AST
    logger.info("Parsing fixture monolith...")
    ast_results = parse_directory(str(SAMPLE_MONOLITH), settings.DEFAULT_LANGUAGE)
    static_edges = extract_static_edges(ast_results)

    # Parse OTel traces
    otel_path = str(SAMPLE_OTEL) if SAMPLE_OTEL.exists() else None
    dynamic_edges = parse_otel_traces(otel_path)

    # Build graph
    logger.info("Building Neo4j graph...")
    communities = await build_graph(ast_results, static_edges, dynamic_edges, SEED_JOB_ID, settings.DEFAULT_LANGUAGE)

    # Embed code
    logger.info("Embedding code into ChromaDB...")
    settings.ensure_dirs()
    num_chunks = embed_and_store(ast_results, str(SAMPLE_MONOLITH), SEED_JOB_ID)
    if communities:
        update_community_ids(SEED_JOB_ID, communities)

    # Summary
    class_count = sum(len(r.get("classes", [])) for r in ast_results)
    method_count = sum(len(r.get("methods", [])) for r in ast_results)
    logger.info("=== Seed Complete ===")
    logger.info("  Files parsed: %d", len(ast_results))
    logger.info("  Classes: %d", class_count)
    logger.info("  Methods: %d", method_count)
    logger.info("  Static edges: %d", len(static_edges))
    logger.info("  Dynamic edges: %d", len(dynamic_edges))
    logger.info("  Communities: %d", len(communities))
    logger.info("  Code chunks embedded: %d", num_chunks)

    await neo4j_client.close()


if __name__ == "__main__":
    asyncio.run(main())
