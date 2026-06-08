# backend/ai/chains/code_chain.py
"""
Code Extraction Chain — LCEL chain for service code generation.

Rewrites monolith classes into standalone microservice code.
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

logger = logging.getLogger(__name__)

_prompts_dir = Path(__file__).parent.parent / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_prompts_dir)))


async def run_code_extraction(
    service_name: str,
    openapi_spec: str,
    source_classes: str,
    language: str = "java",
    framework: str = "springboot",
) -> dict:
    """
    Extract and rewrite monolith classes into microservice code.

    Returns dict: {"files": [{"path": str, "content": str}, ...]}
    """
    llm = get_llm()

    template = _jinja_env.get_template("code_extraction.j2")
    rendered = template.render(
        service_name=service_name,
        openapi_spec=openapi_spec,
        source_classes=source_classes,
        language=language,
        framework=framework,
    )

    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    chain = prompt | llm | JsonOutputParser()

    try:
        result = await chain.ainvoke({"input": rendered})
    except Exception as exc:
        logger.error("Code extraction failed for %s: %s", service_name, exc)
        raise

    # Ensure result has the expected structure
    if isinstance(result, dict) and "files" in result:
        files = result["files"]
    elif isinstance(result, list):
        files = result
    else:
        files = [result]

    logger.info("Code extraction for %s produced %d files", service_name, len(files))
    return {"files": files}
