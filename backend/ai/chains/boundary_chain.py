# backend/ai/chains/boundary_chain.py
"""
Boundary Detection Chain — LCEL chain for DDD bounded context identification.

Uses Gemini to analyse the Neo4j graph + RAG context and propose service boundaries.
Used by orchestrator.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.ai.llm_client import get_llm
from backend.api.schemas import BoundaryProposal

logger = logging.getLogger(__name__)

# Load Jinja2 prompt template
_prompts_dir = Path(__file__).parent.parent / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_prompts_dir)))


def _load_prompt() -> str:
    """Render the boundary detection prompt template."""
    template = _jinja_env.get_template("boundary_detection.j2")
    # Return the raw template string with LangChain-compatible placeholders
    return template.render(
        graph_json="{graph_json}",
        code_chunks="{code_chunks}",
        language="{language}",
        num_services_hint="{num_services_hint}",
    )


async def run_boundary_detection(
    graph_json: str,
    code_chunks: str,
    language: str,
    num_services_hint: int | None = None,
) -> list[BoundaryProposal]:
    """
    Run the boundary detection chain.

    Args:
        graph_json: Neo4j community subgraph as JSON string
        code_chunks: Concatenated RAG-retrieved source snippets
        language: Source language (java, python, etc.)
        num_services_hint: Optional target service count

    Returns:
        List of BoundaryProposal objects
    """
    llm = get_llm()

    # Build the prompt from the Jinja2 template directly
    template = _jinja_env.get_template("boundary_detection.j2")
    rendered = template.render(
        graph_json=graph_json,
        code_chunks=code_chunks,
        language=language,
        num_services_hint=num_services_hint or "",
    )

    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    chain = prompt | llm | JsonOutputParser()

    try:
        result = await chain.ainvoke({"input": rendered})
    except Exception as exc:
        logger.error("Boundary detection chain failed: %s", exc)
        raise

    # Parse into BoundaryProposal objects
    proposals = []
    items = result if isinstance(result, list) else [result]
    for item in items:
        try:
            proposals.append(BoundaryProposal(**item))
        except Exception as exc:
            logger.warning("Failed to parse boundary proposal: %s — %s", item, exc)

    logger.info("Boundary detection produced %d proposals", len(proposals))
    return proposals
