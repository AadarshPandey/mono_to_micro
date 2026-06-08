# backend/ai/chains/contract_chain.py
"""
Contract Generation Chain — LCEL chain for OpenAPI spec generation.

Generates OpenAPI 3.1 YAML for each service boundary.
Used by orchestrator and contracts/openapi_generator.
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


async def run_contract_generation(
    service_name: str,
    classes: list[str],
    code_chunks: str,
    dependencies_on: list[str],
    api_style: str = "REST",
) -> str:
    """
    Generate an OpenAPI 3.1 YAML spec for a service.

    Returns the raw YAML string (validated downstream by contracts/validator).
    """
    llm = get_llm()

    template = _jinja_env.get_template("contract_generation.j2")
    rendered = template.render(
        service_name=service_name,
        classes=classes,
        code_chunks=code_chunks,
        dependencies_on=dependencies_on,
        api_style=api_style,
    )

    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    chain = prompt | llm | StrOutputParser()

    try:
        result = await chain.ainvoke({"input": rendered})
    except Exception as exc:
        logger.error("Contract generation failed for %s: %s", service_name, exc)
        raise

    # Strip markdown fences if the LLM wraps the YAML in them
    yaml_str = _strip_markdown_fences(result)
    logger.info("Generated OpenAPI contract for %s (%d chars)", service_name, len(yaml_str))
    return yaml_str


def _strip_markdown_fences(text: str) -> str:
    """Remove ```yaml ... ``` fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```yaml) and last line (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines)
    return text.strip()
