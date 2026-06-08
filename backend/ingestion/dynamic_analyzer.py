# backend/ingestion/dynamic_analyzer.py
"""
Dynamic Analyzer — OTel/APM trace ingestion.

Parses OpenTelemetry JSON trace exports to extract runtime call frequency
and latency data between classes/methods. Returns weighted dynamic edges.
Used by job_runner.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_otel_traces(file_path: str | None) -> list[dict]:
    """
    Parse an OpenTelemetry JSON export and return weighted dynamic edges.

    Returns list of dicts:
        {source_fqn, target_fqn, call_count, dynamic_weight, latency_p99_ms}

    If file_path is None or file is empty, returns an empty list.
    """
    if file_path is None:
        logger.info("No OTel trace file provided — dynamic analysis skipped")
        return []

    path = Path(file_path)
    if not path.exists() or path.stat().st_size == 0:
        logger.warning("OTel trace file not found or empty: %s", file_path)
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to parse OTel JSON: %s — %s", file_path, exc)
        return []

    # Accumulate call counts and latencies per (source, target) pair
    call_counts: dict[tuple[str, str], int] = defaultdict(int)
    latencies: dict[tuple[str, str], list[float]] = defaultdict(list)

    resource_spans = data.get("resourceSpans", [])
    for rs in resource_spans:
        scope_spans = rs.get("scopeSpans", rs.get("instrumentationLibrarySpans", []))
        for ss in scope_spans:
            spans = ss.get("spans", [])
            for span in spans:
                source = _extract_service_class(span, "source")
                target = _extract_service_class(span, "target")
                if source and target and source != target:
                    pair = (source, target)
                    call_counts[pair] += 1
                    # Duration in nanoseconds → milliseconds
                    start = int(span.get("startTimeUnixNano", 0))
                    end = int(span.get("endTimeUnixNano", 0))
                    if start and end:
                        duration_ms = (end - start) / 1_000_000
                        latencies[pair].append(duration_ms)

    if not call_counts:
        logger.info("No call pairs extracted from OTel traces")
        return []

    # Normalise and build edge list
    edges = _build_edges(call_counts, latencies)
    logger.info("Extracted %d dynamic edges from OTel traces", len(edges))
    return edges


def _extract_service_class(span: dict, role: str) -> str | None:
    """
    Try to extract a class/service name from a span.

    Looks at span attributes for common keys like:
    - code.namespace, code.function, rpc.service, http.route
    - span name as fallback
    """
    attributes = {}
    for attr in span.get("attributes", []):
        key = attr.get("key", "")
        value = attr.get("value", {})
        # OTel attribute values are wrapped in type objects
        str_val = value.get("stringValue") or value.get("intValue") or ""
        attributes[key] = str(str_val)

    if role == "source":
        # Caller: look for parent class/namespace
        return (
            attributes.get("code.namespace")
            or attributes.get("rpc.service")
            or attributes.get("peer.service")
            or _class_from_span_name(span.get("name", ""))
        )
    else:
        # Target: look for the called service
        return (
            attributes.get("rpc.service")
            or attributes.get("peer.service")
            or attributes.get("http.route")
            or _class_from_span_name(span.get("name", ""))
        )


def _class_from_span_name(name: str) -> str | None:
    """Try to extract a class name from a span name like 'ClassName.methodName'."""
    if not name:
        return None
    if "." in name:
        return name.rsplit(".", 1)[0]
    return name


def _build_edges(
    call_counts: dict[tuple[str, str], int],
    latencies: dict[tuple[str, str], list[float]],
) -> list[dict]:
    """Normalise call counts to 0.0-1.0 and compute p99 latency."""
    max_count = max(call_counts.values()) if call_counts else 1

    edges = []
    for (source, target), count in call_counts.items():
        dynamic_weight = count / max_count  # normalised 0.0–1.0

        lat_list = sorted(latencies.get((source, target), []))
        if lat_list:
            p99_idx = int(len(lat_list) * 0.99)
            latency_p99 = lat_list[min(p99_idx, len(lat_list) - 1)]
        else:
            latency_p99 = 0.0

        edges.append({
            "source_fqn": source,
            "target_fqn": target,
            "call_count": count,
            "dynamic_weight": round(dynamic_weight, 4),
            "latency_p99_ms": round(latency_p99, 2),
        })

    return edges
