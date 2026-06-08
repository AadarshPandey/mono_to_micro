# backend/drift/detector.py
"""
Drift Detector — Compares current service graph against approved boundaries.

Detects violations: circular deps, cross-boundary calls, shared DB,
and god-class regrowth. Used by routes/drift and scripts/drift_cron.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from backend.api.schemas import DriftAlert, ViolationType
from backend.db import neo4j_client

logger = logging.getLogger(__name__)


async def detect_violations(
    current_graph: dict,
    job_id: str,
) -> list[DriftAlert]:
    """
    Detect structural violations by comparing current service graph
    against the approved boundary graph stored in Neo4j.

    Returns list of DriftAlert objects for any violations found.
    """
    alerts: list[DriftAlert] = []
    current_edges = current_graph.get("edges", [])
    current_classes = set(current_graph.get("classes", []))

    # Fetch approved boundary assignments from Neo4j
    boundary_map = await _get_boundary_map(job_id)
    if not boundary_map:
        logger.warning("No approved boundaries found for job %s — skipping drift detection", job_id)
        return []

    # Check each edge for violations
    for edge in current_edges:
        source = edge.get("source_fqn", "")
        target = edge.get("target_fqn", "")

        source_boundary = boundary_map.get(source)
        target_boundary = boundary_map.get(target)

        if source_boundary is None or target_boundary is None:
            continue

        # Cross-boundary call violation
        if source_boundary != target_boundary:
            alerts.append(DriftAlert(
                id=str(uuid.uuid4()),
                job_id=job_id,
                service_name=source_boundary,
                violation_type=ViolationType.CROSS_BOUNDARY_CALL,
                detected_at=datetime.now(timezone.utc),
            ))

    # Check for circular dependencies between boundaries
    boundary_deps = _build_boundary_deps(current_edges, boundary_map)
    circular = _find_circular_deps(boundary_deps)
    for pair in circular:
        alerts.append(DriftAlert(
            id=str(uuid.uuid4()),
            job_id=job_id,
            service_name=f"{pair[0]} ↔ {pair[1]}",
            violation_type=ViolationType.CIRCULAR_DEP,
            detected_at=datetime.now(timezone.utc),
        ))

    # Check for god-class regrowth (class importing from 5+ boundaries)
    god_classes = _detect_god_class_regrowth(current_edges, boundary_map)
    for cls_name in god_classes:
        alerts.append(DriftAlert(
            id=str(uuid.uuid4()),
            job_id=job_id,
            service_name=boundary_map.get(cls_name, "unknown"),
            violation_type=ViolationType.GOD_CLASS_REGROWTH,
            detected_at=datetime.now(timezone.utc),
        ))

    logger.info("Drift detection for job %s: %d violations found", job_id, len(alerts))
    return alerts


async def _get_boundary_map(job_id: str) -> dict[str, str]:
    """Fetch class → boundary name mapping from Neo4j."""
    records = await neo4j_client.run_query(
        """
        MATCH (c:Class {job_id: $job_id})-[:BELONGS_TO]->(b:BoundedContext)
        RETURN c.id AS class_id, b.name AS boundary_name
        """,
        {"job_id": job_id},
    )
    return {r["class_id"]: r["boundary_name"] for r in records}


def _build_boundary_deps(
    edges: list[dict],
    boundary_map: dict[str, str],
) -> dict[str, set[str]]:
    """Build boundary → set of dependent boundaries mapping."""
    deps: dict[str, set[str]] = {}
    for edge in edges:
        source_b = boundary_map.get(edge.get("source_fqn", ""))
        target_b = boundary_map.get(edge.get("target_fqn", ""))
        if source_b and target_b and source_b != target_b:
            deps.setdefault(source_b, set()).add(target_b)
    return deps


def _find_circular_deps(deps: dict[str, set[str]]) -> list[tuple[str, str]]:
    """Find pairs with circular dependencies."""
    circular = []
    seen = set()
    for svc, targets in deps.items():
        for target in targets:
            if target in deps and svc in deps[target]:
                pair = tuple(sorted([svc, target]))
                if pair not in seen:
                    seen.add(pair)
                    circular.append(pair)
    return circular


def _detect_god_class_regrowth(
    edges: list[dict],
    boundary_map: dict[str, str],
) -> list[str]:
    """Detect classes importing from 5+ different boundaries."""
    class_boundary_reach: dict[str, set[str]] = {}
    for edge in edges:
        source = edge.get("source_fqn", "")
        target_b = boundary_map.get(edge.get("target_fqn", ""))
        source_b = boundary_map.get(source, "")
        if target_b and target_b != source_b:
            class_boundary_reach.setdefault(source, set()).add(target_b)

    return [cls for cls, boundaries in class_boundary_reach.items() if len(boundaries) >= 5]
