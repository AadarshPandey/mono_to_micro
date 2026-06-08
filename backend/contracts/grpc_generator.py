# backend/contracts/grpc_generator.py
"""
gRPC Generator — Generates Protobuf .proto files for high-throughput pairs.

Creates .proto definitions for service pairs using gRPC communication.
Used by orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.ai.llm_client import get_llm
from backend.api.schemas import BoundaryProposal
from backend.config import settings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

_GRPC_PROMPT = """You are an expert Protocol Buffers and gRPC designer.

Generate a .proto file (proto3 syntax) for the "{service_name}" service.

Classes in this service: {classes}
Dependencies on: {dependencies}

Instructions:
1. Use proto3 syntax.
2. Define a service with RPCs for all CRUD operations implied by the classes.
3. Define message types for requests, responses, and domain entities.
4. Use appropriate field types (string, int64, bool, repeated, etc.).
5. Add comments describing each RPC and message.
6. Return ONLY the .proto file content, no markdown fences.
"""


async def generate_proto(
    boundary: BoundaryProposal | dict,
    job_id: str,
) -> str | None:
    """
    Generate a .proto file for a gRPC service.
    Returns proto content string or None if not applicable.
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

    # Only generate for gRPC services
    if "grpc" not in api_style.lower():
        return None

    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([("human", _GRPC_PROMPT)])
    chain = prompt | llm | StrOutputParser()

    try:
        result = await chain.ainvoke({
            "service_name": name,
            "classes": ", ".join(classes),
            "dependencies": ", ".join(deps) if deps else "None",
        })
    except Exception as exc:
        logger.error("gRPC proto generation failed for %s: %s", name, exc)
        return None

    # Strip markdown fences
    proto_str = result.strip()
    if proto_str.startswith("```"):
        lines = proto_str.split("\n")
        proto_str = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # Save to disk
    output_dir = Path(settings.OUTPUT_DIR) / job_id / "contracts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name.lower()}.proto"
    output_path.write_text(proto_str, encoding="utf-8")
    logger.info("Saved .proto for %s", name)

    return proto_str
