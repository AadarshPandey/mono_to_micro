# backend/scaffolding/infra_generator.py
"""
Infra Generator — Generates Dockerfile, K8s YAML, Docker Compose block.

Renders infrastructure templates for each scaffolded service.
Used by orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend.config import settings

logger = logging.getLogger(__name__)

_templates_dir = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_templates_dir)))


def render_dockerfile(
    service_name: str,
    language: str,
    port: int,
    java_version: str = "17",
    python_version: str = "3.11",
) -> str:
    """Render a Dockerfile for a service."""
    tmpl = _jinja_env.get_template("dockerfile.j2")
    return tmpl.render(
        service_name=service_name,
        language=language,
        port=port,
        java_version=java_version,
        python_version=python_version,
    )


def render_k8s(
    service_name: str,
    port: int,
    image_name: str | None = None,
    replicas: int = 2,
    cpu_request: str = "250m",
    memory_request: str = "512Mi",
    readiness_path: str = "/health",
) -> str:
    """Render K8s Deployment + Service YAML for a service."""
    if image_name is None:
        image_name = f"your-registry/{service_name.lower().replace(' ', '-')}:latest"

    tmpl = _jinja_env.get_template("k8s_deployment.j2")
    return tmpl.render(
        service_name=service_name,
        image_name=image_name,
        port=port,
        replicas=replicas,
        cpu_request=cpu_request,
        memory_request=memory_request,
        readiness_path=readiness_path,
    )


def render_compose_block(
    service_name: str,
    port: int,
    dependencies: list[str] | None = None,
) -> str:
    """Render a docker-compose service block."""
    tmpl = _jinja_env.get_template("docker_compose_svc.j2")
    return tmpl.render(
        service_name=service_name,
        port=port,
        dependencies=dependencies or [],
    )


def generate_all_infra(
    service_name: str,
    language: str,
    port: int,
    dependencies: list[str] | None = None,
    job_id: str = "",
) -> dict[str, str]:
    """
    Generate all infra files for a service and write to disk.
    Returns dict of {filename: content}.
    """
    service_slug = service_name.lower().replace(" ", "-")
    output_dir = Path(settings.OUTPUT_DIR) / job_id / "services" / service_slug / "infra"
    output_dir.mkdir(parents=True, exist_ok=True)

    infra_files = {}

    # Dockerfile
    dockerfile = render_dockerfile(service_name, language, port)
    (output_dir.parent / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    infra_files["Dockerfile"] = dockerfile

    # K8s
    k8s = render_k8s(service_name, port)
    (output_dir / "k8s-deployment.yaml").write_text(k8s, encoding="utf-8")
    infra_files["k8s-deployment.yaml"] = k8s

    # Docker Compose block
    compose = render_compose_block(service_name, port, dependencies)
    (output_dir / "docker-compose-service.yaml").write_text(compose, encoding="utf-8")
    infra_files["docker-compose-service.yaml"] = compose

    logger.info("Generated infra files for %s", service_name)
    return infra_files
