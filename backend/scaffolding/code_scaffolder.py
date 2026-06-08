# backend/scaffolding/code_scaffolder.py
"""
Code Scaffolder — Renders Jinja2 code templates with LLM-generated logic.

Merges LLM-generated code with framework-specific template structure.
Used by orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend.api.schemas import GeneratedFile
from backend.config import settings

logger = logging.getLogger(__name__)

_templates_dir = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_templates_dir)))

# Port assignment counter (starts at 8081, incremented per service)
_next_port = 8081


def render_service(
    service_name: str,
    language: str,
    generated_files: list[dict],
    openapi_spec: str,
    dependencies: list[str] | None = None,
    job_id: str = "",
) -> list[GeneratedFile]:
    """
    Render a complete service from templates + LLM-generated code.

    Returns list of GeneratedFile objects with path and content.
    """
    global _next_port
    port = _next_port
    _next_port += 1

    framework = "springboot" if language == "java" else "fastapi"
    package_name = f"com.example.{service_name.lower().replace(' ', '')}"
    service_slug = service_name.lower().replace(" ", "-")

    all_files: list[GeneratedFile] = []

    # Render framework templates
    if language == "java":
        all_files.extend(_render_java_templates(
            service_name=service_name,
            package_name=package_name,
            port=port,
            dependencies=dependencies or [],
        ))
    else:
        all_files.extend(_render_python_templates(
            service_name=service_name,
            port=port,
            dependencies=dependencies or [],
        ))

    # Add LLM-generated code files
    for f in generated_files:
        path = f.get("path", "")
        content = f.get("content", "")
        if path and content:
            all_files.append(GeneratedFile(path=path, content=content))

    # Write all files to output directory
    output_dir = Path(settings.OUTPUT_DIR) / job_id / "services" / service_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    for gf in all_files:
        file_path = output_dir / gf.path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(gf.content, encoding="utf-8")

    logger.info("Scaffolded %d files for %s at port %d", len(all_files), service_name, port)
    return all_files


def _render_java_templates(
    service_name: str,
    package_name: str,
    port: int,
    dependencies: list[str],
) -> list[GeneratedFile]:
    """Render Java Spring Boot project templates."""
    files = []
    ctx = {
        "service_name": service_name,
        "package_name": package_name,
        "port": port,
        "dependencies": dependencies,
        "java_version": "17",
        "spring_boot_version": "3.2.0",
    }

    templates = {
        "pom.xml": "java_springboot/pom.xml.j2",
        f"src/main/java/{package_name.replace('.', '/')}/Application.java": "java_springboot/Application.java.j2",
        "src/main/resources/application.yml": "java_springboot/application.yml.j2",
    }

    for output_path, template_name in templates.items():
        try:
            tmpl = _jinja_env.get_template(template_name)
            content = tmpl.render(**ctx)
            files.append(GeneratedFile(path=output_path, content=content))
        except Exception as exc:
            logger.warning("Failed to render %s: %s", template_name, exc)

    return files


def _render_python_templates(
    service_name: str,
    port: int,
    dependencies: list[str],
) -> list[GeneratedFile]:
    """Render Python FastAPI project templates."""
    files = []
    ctx = {
        "service_name": service_name,
        "port": port,
        "dependencies": dependencies,
        "python_version": "3.11",
    }

    templates = {
        "pyproject.toml": "python_fastapi/pyproject.toml.j2",
        "main.py": "python_fastapi/main.py.j2",
        "router.py": "python_fastapi/router.py.j2",
        "service.py": "python_fastapi/service.py.j2",
        "models.py": "python_fastapi/models.py.j2",
    }

    for output_path, template_name in templates.items():
        try:
            tmpl = _jinja_env.get_template(template_name)
            content = tmpl.render(**ctx)
            files.append(GeneratedFile(path=output_path, content=content))
        except Exception as exc:
            logger.warning("Failed to render %s: %s", template_name, exc)

    return files


def reset_port_counter() -> None:
    """Reset the port counter (useful for testing)."""
    global _next_port
    _next_port = 8081
