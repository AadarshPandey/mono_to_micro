# scripts/export_graph.py
"""
Export Graph — Dumps Neo4j boundary graph as JSON.

Usage: python scripts/export_graph.py --job-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.db import neo4j_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def export_graph(job_id: str) -> None:
    """Export the boundary graph for a job as JSON."""
    await neo4j_client.get_driver()

    # Fetch bounded contexts
    boundaries = await neo4j_client.run_query(
        """
        MATCH (c:Class {job_id: $job_id})
        RETURN c.community_id AS community_id,
               collect(c.id) AS class_ids,
               collect(c.name) AS class_names
        ORDER BY community_id
        """,
        {"job_id": job_id},
    )

    # Fetch edges
    edges = await neo4j_client.run_query(
        """
        MATCH (a:Class {job_id: $job_id})-[r:IMPORTS|CALLS]->(b:Class {job_id: $job_id})
        RETURN a.id AS source, b.id AS target, type(r) AS edge_type,
               r.combined_weight AS weight
        """,
        {"job_id": job_id},
    )

    export = {
        "boundaries": [
            {
                "community_id": b["community_id"],
                "classes": b["class_ids"],
                "class_names": b["class_names"],
            }
            for b in boundaries
        ],
        "edges": [
            {
                "source": e["source"],
                "target": e["target"],
                "type": e["edge_type"],
                "weight": e["weight"],
            }
            for e in edges
        ],
        "metadata": {
            "job_id": job_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "boundary_count": len(boundaries),
            "edge_count": len(edges),
        },
    }

    # Write output
    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"graph_export_{job_id}.json"
    output_path.write_text(json.dumps(export, indent=2), encoding="utf-8")

    logger.info("Exported graph to %s", output_path)
    logger.info("  Boundaries: %d, Edges: %d", len(boundaries), len(edges))

    await neo4j_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Neo4j boundary graph as JSON")
    parser.add_argument("--job-id", required=True, help="Job ID to export")
    args = parser.parse_args()
    asyncio.run(export_graph(args.job_id))
