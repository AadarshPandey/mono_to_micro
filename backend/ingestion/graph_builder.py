# backend/ingestion/graph_builder.py
"""
Graph Builder — Neo4j knowledge graph construction + Louvain clustering.

Merges static AST edges and dynamic OTel edges into a weighted Neo4j graph,
then runs Louvain community detection. Used by job_runner.
"""

from __future__ import annotations

import logging

from backend.config import settings
from backend.db import neo4j_client

logger = logging.getLogger(__name__)


async def build_graph(
    ast_results: list[dict],
    static_edges: list[dict],
    dynamic_edges: list[dict],
    job_id: str,
    language: str,
) -> list[dict]:
    """
    Full graph build pipeline:
    1. Create :Class nodes
    2. Create :Method nodes
    3. Create :IMPORTS / :CALLS edges with weights
    4. Compute combined_weight
    5. Run Louvain clustering
    Returns list of community dicts: [{community_id, class_ids: [...]}]
    """
    await create_class_nodes(ast_results, job_id, language)
    await create_method_nodes(ast_results, job_id)
    await create_edges(static_edges, dynamic_edges, job_id)
    await compute_combined_weights(job_id)
    communities = await run_louvain(job_id)
    logger.info("Graph built for job %s: %d communities", job_id, len(communities))
    return communities


async def create_class_nodes(ast_results: list[dict], job_id: str, language: str) -> None:
    """MERGE :Class nodes from AST parse results."""
    for result in ast_results:
        for cls in result.get("classes", []):
            await neo4j_client.run_write(
                """
                MERGE (c:Class {id: $id})
                SET c.name = $name,
                    c.file_path = $file_path,
                    c.language = $language,
                    c.job_id = $job_id
                """,
                {
                    "id": cls.get("fqn", cls["name"]),
                    "name": cls["name"],
                    "file_path": cls.get("file_path", ""),
                    "language": language,
                    "job_id": job_id,
                },
            )
    logger.info("Created class nodes for job %s", job_id)


async def create_method_nodes(ast_results: list[dict], job_id: str) -> None:
    """MERGE :Method nodes from AST parse results."""
    for result in ast_results:
        for method in result.get("methods", []):
            await neo4j_client.run_write(
                """
                MERGE (m:Method {id: $id})
                SET m.name = $name,
                    m.class_id = $class_id,
                    m.return_type = $return_type,
                    m.job_id = $job_id
                """,
                {
                    "id": method.get("fqn", f"{method.get('class_name', '')}#{method['name']}"),
                    "name": method["name"],
                    "class_id": method.get("class_name", ""),
                    "return_type": method.get("return_type", "void"),
                    "job_id": job_id,
                },
            )
    logger.info("Created method nodes for job %s", job_id)


async def create_edges(
    static_edges: list[dict],
    dynamic_edges: list[dict],
    job_id: str,
) -> None:
    """Create :IMPORTS and :CALLS relationships with static + dynamic weights."""
    # Index dynamic edges for fast lookup
    dynamic_map: dict[tuple[str, str], dict] = {}
    for de in dynamic_edges:
        key = (de["source_fqn"], de["target_fqn"])
        dynamic_map[key] = de

    for edge in static_edges:
        source = edge["source_fqn"]
        target = edge["target_fqn"]
        edge_type = edge["edge_type"]

        # Look up dynamic data
        dyn = dynamic_map.get((source, target), {})
        dyn_weight = dyn.get("dynamic_weight", 0.0)
        call_count = dyn.get("call_count", 0)
        latency = dyn.get("latency_p99_ms", 0.0)

        rel_type = "IMPORTS" if edge_type == "IMPORTS" else "CALLS"

        await neo4j_client.run_write(
            f"""
            MATCH (a:Class {{id: $source, job_id: $job_id}})
            MATCH (b:Class {{id: $target, job_id: $job_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r.static_weight = 1,
                r.dynamic_weight = $dyn_weight,
                r.call_count = $call_count,
                r.latency_p99_ms = $latency,
                r.job_id = $job_id
            """,
            {
                "source": source,
                "target": target,
                "dyn_weight": dyn_weight,
                "call_count": call_count,
                "latency": latency,
                "job_id": job_id,
            },
        )

    # Also create edges for dynamic-only pairs (no static edge)
    static_pairs = {(e["source_fqn"], e["target_fqn"]) for e in static_edges}
    for de in dynamic_edges:
        pair = (de["source_fqn"], de["target_fqn"])
        if pair not in static_pairs:
            await neo4j_client.run_write(
                """
                MATCH (a:Class {id: $source, job_id: $job_id})
                MATCH (b:Class {id: $target, job_id: $job_id})
                MERGE (a)-[r:CALLS]->(b)
                SET r.static_weight = 0,
                    r.dynamic_weight = $dyn_weight,
                    r.call_count = $call_count,
                    r.latency_p99_ms = $latency,
                    r.job_id = $job_id
                """,
                {
                    "source": de["source_fqn"],
                    "target": de["target_fqn"],
                    "dyn_weight": de["dynamic_weight"],
                    "call_count": de["call_count"],
                    "latency": de["latency_p99_ms"],
                    "job_id": job_id,
                },
            )

    logger.info("Created edges for job %s", job_id)


async def compute_combined_weights(job_id: str) -> None:
    """Set combined_weight on all edges: static_weight + (dynamic_weight * multiplier)."""
    multiplier = settings.DYNAMIC_WEIGHT_MULTIPLIER
    for rel_type in ("IMPORTS", "CALLS"):
        await neo4j_client.run_write(
            f"""
            MATCH ()-[r:{rel_type} {{job_id: $job_id}}]->()
            SET r.combined_weight = r.static_weight + (r.dynamic_weight * $multiplier)
            """,
            {"job_id": job_id, "multiplier": multiplier},
        )
    logger.info("Computed combined weights for job %s (multiplier=%.1f)", job_id, multiplier)


async def run_louvain(job_id: str) -> list[dict]:
    """
    Run Louvain community detection via Neo4j GDS plugin.
    Falls back to connected-component assignment if GDS is unavailable.
    Returns list of community dicts: [{community_id, class_ids}]
    """
    try:
        # Try GDS Louvain
        await neo4j_client.run_write(
            """
            CALL gds.graph.project(
                $graph_name,
                {Class: {properties: ['job_id']}},
                {IMPORTS: {orientation: 'UNDIRECTED', properties: ['combined_weight']},
                 CALLS:   {orientation: 'UNDIRECTED', properties: ['combined_weight']}}
            )
            """,
            {"graph_name": f"louvain_{job_id}"},
        )

        await neo4j_client.run_write(
            """
            CALL gds.louvain.write($graph_name, {
                writeProperty: 'community_id',
                relationshipWeightProperty: 'combined_weight'
            })
            """,
            {"graph_name": f"louvain_{job_id}"},
        )

        # Clean up projected graph
        await neo4j_client.run_write(
            "CALL gds.graph.drop($graph_name)",
            {"graph_name": f"louvain_{job_id}"},
        )

        logger.info("Louvain clustering completed via GDS for job %s", job_id)

    except Exception as exc:
        logger.warning("GDS Louvain failed (%s) — falling back to file-based communities", exc)
        # Fallback: assign community_id based on file path grouping
        await neo4j_client.run_write(
            """
            MATCH (c:Class {job_id: $job_id})
            WITH c, c.file_path AS fp
            WITH collect(c) AS classes, fp
            WITH classes, fp, id(classes[0]) % 100 AS community
            UNWIND classes AS c
            SET c.community_id = community
            """,
            {"job_id": job_id},
        )

    # Fetch communities
    records = await neo4j_client.run_query(
        """
        MATCH (c:Class {job_id: $job_id})
        RETURN c.community_id AS community_id, collect(c.id) AS class_ids
        ORDER BY community_id
        """,
        {"job_id": job_id},
    )

    return [{"community_id": r["community_id"], "class_ids": r["class_ids"]} for r in records]
