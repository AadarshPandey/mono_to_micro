# backend/ai/chains/strangler_chain.py
"""
Strangler-Fig Chain — LCEL chain for migration plan generation.

Generates facade adapter + phased migration plan.
Uses temperature=0.4 for more natural prose.
Used by orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.ai.llm_client import get_llm

logger = logging.getLogger(__name__)

_prompts_dir = Path(__file__).parent.parent / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_prompts_dir)))


async def run_strangler_plan(
    service_name: str,
    boundary: dict,
    original_imports: str,
    api_endpoints: str,
) -> str:
    """
    Generate a strangler-fig migration plan with facade adapter.

    Uses temperature=0.4 for more natural prose output.
    Returns Markdown string.
    """
    # Use higher temperature for natural prose
    llm = get_llm(temperature=0.4)

    template = _jinja_env.get_template("strangler_plan.j2")
    rendered = template.render(
        service_name=service_name,
        boundary=boundary,
        original_imports=original_imports,
        api_endpoints=api_endpoints,
    )

    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    chain = prompt | llm | StrOutputParser()

    try:
        result = await chain.ainvoke({"input": rendered})
    except Exception as exc:
        logger.error("Strangler plan generation failed for %s: %s", service_name, exc)
        raise

    logger.info("Generated strangler plan for %s (%d chars)", service_name, len(result))
    return result
