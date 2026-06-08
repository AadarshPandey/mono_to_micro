# backend/contracts/asyncapi_generator.py
"""
AsyncAPI Generator — Generates AsyncAPI specs for event-driven service pairs.

Generates AsyncAPI 2.x channel definitions for services using event-driven
communication patterns (Kafka/RabbitMQ). Used by orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from backend.ai.llm_client import get_llm
from backend.api.schemas import BoundaryProposal
from backend.config import settings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

_ASYNCAPI_PROMPT = """You are an expert event-driven architecture designer.

Generate an AsyncAPI 2.6.0 YAML specification for the "{service_name}" service.

Classes in this service: {classes}
Dependencies on: {dependencies}

Instructions:
1. Define publish channels for events this service emits (e.g., OrderCreated, OrderUpdated).
2. Define subscribe channels for events this service consumes.
3. Use Kafka as the default protocol.
4. Include message schemas based on the class DTOs.
5. Return ONLY valid AsyncAPI YAML, no markdown fences.
"""


async def generate_asyncapi(
    boundary: BoundaryProposal | dict,
    job_id: str,
) -> str | None:
    """
    Generate an AsyncAPI spec for an event-driven service.
    Returns YAML string or None if not applicable.
    """
    if isinstance(boundary, dict):
        name = boundary.get("name", "")
        classes = boundary.get("classes", [])
        deps = boundary.get("dependencies_on", [])
        api_style = boundary.get("suggested_api_style", "REST")
    else:
        name = boundary.name
        classes = boundary.classes
        deps = boundary.dependencies_on
        api_style = str(boundary.suggested_api_style)

    # Only generate for event-driven services
    if "event" not in api_style.lower():
        return None

    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([("human", _ASYNCAPI_PROMPT)])
    chain = prompt | llm | StrOutputParser()

    try:
        result = await chain.ainvoke({
            "service_name": name,
            "classes": ", ".join(classes),
            "dependencies": ", ".join(deps) if deps else "None",
        })
    except Exception as exc:
        logger.error("AsyncAPI generation failed for %s: %s", name, exc)
        return None

    # Strip markdown fences
    yaml_str = result.strip()
    if yaml_str.startswith("```"):
        lines = yaml_str.split("\n")
        yaml_str = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # Save to disk
    output_dir = Path(settings.OUTPUT_DIR) / job_id / "contracts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name.lower()}.asyncapi.yaml"
    output_path.write_text(yaml_str, encoding="utf-8")
    logger.info("Saved AsyncAPI spec for %s", name)

    return yaml_str
