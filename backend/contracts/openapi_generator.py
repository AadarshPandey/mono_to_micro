# backend/contracts/openapi_generator.py
"""
OpenAPI Generator — Calls contract_chain, validates output, saves YAML.

Orchestrates the end-to-end OpenAPI generation for each boundary.
Used by orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from backend.ai.chains.contract_chain import run_contract_generation
from backend.ai.rag_retriever import retrieve_for_boundary
from backend.api.schemas import BoundaryProposal, ContractSpec
from backend.config import settings
from backend.contracts.validator import validate_openapi

logger = logging.getLogger(__name__)


async def generate_openapi(
    boundary: BoundaryProposal | dict,
    job_id: str,
) -> ContractSpec:
    """
    Generate and validate an OpenAPI spec for a service boundary.

    1. Retrieve code context via RAG
    2. Call contract_chain to generate YAML
    3. Validate with openapi-spec-validator
    4. Save to output directory
    5. Return ContractSpec
    """
    if isinstance(boundary, dict):
        name = boundary.get("name", "Unknown")
        classes = boundary.get("classes", [])
        deps = boundary.get("dependencies_on", [])
        api_style = boundary.get("suggested_api_style", "REST")
    else:
        name = boundary.name
        classes = boundary.classes
        deps = boundary.dependencies_on
        api_style = boundary.suggested_api_style.value if hasattr(boundary.suggested_api_style, 'value') else str(boundary.suggested_api_style)

    # 1. Get code context
    code_chunks = retrieve_for_boundary(boundary, job_id)

    # 2. Generate contract
    yaml_str = await run_contract_generation(
        service_name=name,
        classes=classes,
        code_chunks=code_chunks,
        dependencies_on=deps,
        api_style=api_style,
    )

    # 3. Validate
    result = validate_openapi(yaml_str)
    if not result["valid"]:
        logger.warning(
            "Generated OpenAPI for %s has validation errors: %s — using as-is",
            name, result["errors"],
        )

    # 4. Save to disk
    output_dir = Path(settings.OUTPUT_DIR) / job_id / "contracts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name.lower()}.openapi.yaml"
    output_path.write_text(yaml_str, encoding="utf-8")
    logger.info("Saved OpenAPI spec to %s", output_path)

    return ContractSpec(
        service_name=name,
        openapi_yaml=yaml_str,
    )
