# backend/scaffolding/strangler_planner.py
"""
Strangler Planner — Generates facade adapter + migration checklist.

Wraps the strangler_chain output into structured files.
Used by orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.ai.chains.strangler_chain import run_strangler_plan
from backend.config import settings

logger = logging.getLogger(__name__)


async def generate_migration_plan(
    service_name: str,
    boundary: dict,
    openapi_spec: str,
    original_imports: list[dict] | None = None,
    job_id: str = "",
) -> str:
    """
    Generate a strangler-fig migration plan for a service.

    Calls the strangler_chain and writes the output to MIGRATION.md.
    Returns the Markdown plan string.
    """
    # Format original imports as readable text
    imports_text = ""
    if original_imports:
        imports_text = "\n".join(
            f"- {imp.get('source_fqn', '?')} → {imp.get('target_fqn', '?')}"
            for imp in original_imports
        )
    else:
        imports_text = "(No cross-boundary imports detected)"

    # Format API endpoints from openapi spec
    endpoints_text = _extract_endpoints_summary(openapi_spec)

    # Call the LLM chain
    plan_md = await run_strangler_plan(
        service_name=service_name,
        boundary=boundary,
        original_imports=imports_text,
        api_endpoints=endpoints_text,
    )

    # Write to disk
    service_slug = service_name.lower().replace(" ", "-")
    output_dir = Path(settings.OUTPUT_DIR) / job_id / "services" / service_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    migration_path = output_dir / "MIGRATION.md"
    migration_path.write_text(plan_md, encoding="utf-8")
    logger.info("Saved migration plan for %s", service_name)

    return plan_md


def _extract_endpoints_summary(openapi_yaml: str) -> str:
    """Extract a readable endpoint summary from OpenAPI YAML."""
    try:
        import yaml
        spec = yaml.safe_load(openapi_yaml)
        if not isinstance(spec, dict) or "paths" not in spec:
            return "(No endpoints parsed)"

        lines = []
        for path, methods in spec.get("paths", {}).items():
            if isinstance(methods, dict):
                for method, details in methods.items():
                    if method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                        summary = details.get("summary", "") if isinstance(details, dict) else ""
                        lines.append(f"- {method.upper()} {path}: {summary}")
        return "\n".join(lines) if lines else "(No endpoints found)"
    except Exception:
        return "(Could not parse OpenAPI spec)"
