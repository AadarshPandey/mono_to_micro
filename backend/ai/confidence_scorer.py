# backend/ai/confidence_scorer.py
"""
Confidence Scorer — Scores boundary proposals on cohesion vs coupling.

Queries Neo4j to count internal vs external edges for each boundary,
computes confidence scores, and flags low-confidence clusters.
Used by orchestrator.
"""

from __future__ import annotations

import logging

from backend.api.schemas import BoundaryProposal, ConfidenceScore
from backend.config import settings
from backend.db import neo4j_client

logger = logging.getLogger(__name__)


async def score_all_boundaries(
    boundaries: list[BoundaryProposal] | list[dict],
    job_id: str,
) -> list[ConfidenceScore]:
    """
    Score all boundary proposals and return confidence scores.
    Clusters below CONFIDENCE_THRESHOLD are flagged for mandatory review.
    """
    scores = []
    for boundary in boundaries:
        score = await score_boundary(boundary, job_id)
        scores.append(score)

    flagged_count = sum(1 for s in scores if s.flagged)
    logger.info(
        "Scored %d boundaries for job %s: %d flagged (threshold=%.2f)",
        len(scores), job_id, flagged_count, settings.CONFIDENCE_THRESHOLD,
    )
    return scores


async def score_boundary(
    boundary: BoundaryProposal | dict,
    job_id: str,
) -> ConfidenceScore:
    """
    Compute confidence for a single boundary cluster.

    Formula:
        cohesion   = internal_edges / total_possible_internal_edges
        coupling   = external_edges / total_edges_touching
        confidence = cohesion * (1 - coupling)
    """
    if isinstance(boundary, dict):
        name = boundary.get("name", "Unknown")
        classes = boundary.get("classes", [])
    else:
        name = boundary.name
        classes = boundary.classes

    if len(classes) < 2:
        # Single-class boundary: perfect cohesion, measure coupling only
        coupling = await _compute_coupling(classes, job_id)
        return ConfidenceScore(
            boundary_name=name,
            cohesion=1.0,
            coupling=coupling,
            confidence=1.0 * (1 - coupling),
            flagged=(1.0 * (1 - coupling)) < settings.CONFIDENCE_THRESHOLD,
        )

    # Count internal edges (between classes in this boundary)
    internal_edges = await _count_internal_edges(classes, job_id)

    # Total possible internal edges (undirected): n*(n-1)/2
    n = len(classes)
    total_possible = n * (n - 1) / 2 if n > 1 else 1

    # Count external edges (from classes in boundary to classes outside)
    external_edges = await _count_external_edges(classes, job_id)

    total_touching = internal_edges + external_edges

    # Compute scores
    cohesion = internal_edges / total_possible if total_possible > 0 else 0.0
    coupling = external_edges / total_touching if total_touching > 0 else 0.0
    confidence = cohesion * (1.0 - coupling)
    flagged = confidence < settings.CONFIDENCE_THRESHOLD

    return ConfidenceScore(
        boundary_name=name,
        cohesion=round(cohesion, 4),
        coupling=round(coupling, 4),
        confidence=round(confidence, 4),
        flagged=flagged,
    )


async def detect_god_classes(
    boundaries: list[BoundaryProposal] | list[dict],
    job_id: str,
) -> list[str]:
    """
    Detect god classes — classes with imports touching >5 community clusters.
    Returns list of class FQNs that are god classes.
    """
    # Collect all class → boundary mapping
    class_to_boundary: dict[str, str] = {}
    for b in boundaries:
        name = b.get("name", b.name) if isinstance(b, dict) else b.name
        classes = b.get("classes", b.classes) if isinstance(b, dict) else b.classes
        for cls in classes:
            class_to_boundary[cls] = name

    god_classes = []
    for cls_name in class_to_boundary:
        # Count how many distinct boundaries this class connects to
        records = await neo4j_client.run_query(
            """
            MATCH (c:Class {id: $class_id, job_id: $job_id})-[:IMPORTS|CALLS]-(other:Class {job_id: $job_id})
            RETURN DISTINCT other.id AS connected_class
            """,
            {"class_id": cls_name, "job_id": job_id},
        )

        connected_boundaries = set()
        for r in records:
            connected_cls = r["connected_class"]
            if connected_cls in class_to_boundary:
                connected_boundaries.add(class_to_boundary[connected_cls])

        # Remove own boundary
        own_boundary = class_to_boundary.get(cls_name, "")
        connected_boundaries.discard(own_boundary)

        if len(connected_boundaries) >= 5:
            god_classes.append(cls_name)
            logger.warning("God class detected: %s (touches %d boundaries)", cls_name, len(connected_boundaries))

    return god_classes


# ── Private helpers ────────────────────────────────────────────────────────


async def _count_internal_edges(classes: list[str], job_id: str) -> int:
    """Count edges between classes within the same boundary."""
    records = await neo4j_client.run_query(
        """
        MATCH (a:Class {job_id: $job_id})-[r:IMPORTS|CALLS]->(b:Class {job_id: $job_id})
        WHERE a.id IN $classes AND b.id IN $classes AND a.id <> b.id
        RETURN count(r) AS cnt
        """,
        {"classes": classes, "job_id": job_id},
    )
    return records[0]["cnt"] if records else 0


async def _count_external_edges(classes: list[str], job_id: str) -> int:
    """Count edges from boundary classes to classes outside the boundary."""
    records = await neo4j_client.run_query(
        """
        MATCH (a:Class {job_id: $job_id})-[r:IMPORTS|CALLS]-(b:Class {job_id: $job_id})
        WHERE a.id IN $classes AND NOT b.id IN $classes
        RETURN count(r) AS cnt
        """,
        {"classes": classes, "job_id": job_id},
    )
    return records[0]["cnt"] if records else 0


async def _compute_coupling(classes: list[str], job_id: str) -> float:
    """Compute coupling ratio for a set of classes."""
    external = await _count_external_edges(classes, job_id)
    internal = await _count_internal_edges(classes, job_id)
    total = external + internal
    return external / total if total > 0 else 0.0
