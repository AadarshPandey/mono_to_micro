# backend/db/neo4j_client.py
"""
Neo4j Client — Async driver, connection pool, and query helpers.

Provides a singleton async Neo4j driver with helper methods for read/write
queries and migration execution. Used by graph_builder, confidence_scorer,
drift modules, and scripts.
"""

from __future__ import annotations

import logging
from pathlib import Path

from neo4j import AsyncDriver, AsyncGraphDatabase

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Driver management ─────────────────────────────────────────────────────

_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    """Return the singleton async Neo4j driver, creating it on first call."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        # Verify connectivity
        await _driver.verify_connectivity()
        logger.info("Neo4j driver connected to %s", settings.NEO4J_URI)
    return _driver


async def close() -> None:
    """Close the Neo4j driver pool — call on app shutdown."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


# ── Query helpers ──────────────────────────────────────────────────────────


async def run_query(cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a read query and return a list of record dicts."""
    driver = await get_driver()
    async with driver.session(database=settings.NEO4J_DATABASE) as session:
        result = await session.run(cypher, parameters=params or {})
        records = await result.data()
        return records


async def run_write(cypher: str, params: dict | None = None) -> None:
    """Execute a write query (CREATE, MERGE, SET, DELETE)."""
    driver = await get_driver()
    async with driver.session(database=settings.NEO4J_DATABASE) as session:
        await session.run(cypher, parameters=params or {})


async def run_write_batch(statements: list[tuple[str, dict]]) -> None:
    """Execute multiple write statements in a single transaction."""
    driver = await get_driver()
    async with driver.session(database=settings.NEO4J_DATABASE) as session:
        async with session.begin_transaction() as tx:
            for cypher, params in statements:
                await tx.run(cypher, parameters=params)
            await tx.commit()


# ── Migrations ─────────────────────────────────────────────────────────────


async def run_migrations() -> None:
    """Execute all .cypher migration files in db/migrations/ in sorted order."""
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        logger.warning("Migrations directory not found: %s", migrations_dir)
        return

    migration_files = sorted(migrations_dir.glob("*.cypher"))
    driver = await get_driver()

    for mig_file in migration_files:
        cypher_text = mig_file.read_text().strip()
        if not cypher_text or cypher_text.startswith("//"):
            logger.info("Skipping comment-only migration: %s", mig_file.name)
            continue

        # Split on semicolons for multi-statement files
        statements = [s.strip() for s in cypher_text.split(";") if s.strip() and not s.strip().startswith("//")]
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            for stmt in statements:
                try:
                    await session.run(stmt)
                except Exception as exc:
                    logger.error("Migration %s failed on statement: %s — %s", mig_file.name, stmt[:80], exc)
                    raise
        logger.info("Applied migration: %s", mig_file.name)
