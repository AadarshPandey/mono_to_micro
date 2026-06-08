# backend/drift/scanner.py
"""
Drift Scanner — Scans a deployed service repo to build its current dependency graph.

Uses the AST parser to analyse the current state of a service and produce
a dependency snapshot for comparison against approved boundaries.
Used by routes/drift and scripts/drift_cron.
"""

from __future__ import annotations

import logging

from backend.config import settings
from backend.ingestion.ast_parser import extract_static_edges, parse_directory
from backend.ingestion.language_registry import detect_language

logger = logging.getLogger(__name__)


def scan_service_repo(
    repo_path: str,
    language: str | None = None,
) -> dict:
    """
    Scan a service repository and return its current dependency graph.

    Returns dict with:
        - classes: list of class FQNs found
        - edges: list of {source_fqn, target_fqn, edge_type} dependency edges
        - file_count: number of files scanned
    """
    lang = language or settings.DEFAULT_LANGUAGE

    try:
        ast_results = parse_directory(repo_path, lang)
    except FileNotFoundError:
        logger.error("Service repo not found: %s", repo_path)
        return {"classes": [], "edges": [], "file_count": 0}

    edges = extract_static_edges(ast_results)

    # Collect all class names
    classes = []
    for result in ast_results:
        for cls in result.get("classes", []):
            classes.append(cls.get("fqn", cls["name"]))

    logger.info(
        "Scanned %s: %d files, %d classes, %d edges",
        repo_path, len(ast_results), len(classes), len(edges),
    )

    return {
        "classes": classes,
        "edges": edges,
        "file_count": len(ast_results),
    }
