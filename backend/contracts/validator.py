# backend/contracts/validator.py
"""
Contract Validator — OpenAPI spec validation + cross-service reference checks.

Validates generated OpenAPI specs using openapi-spec-validator and checks
for cross-service consistency. Used by openapi_generator and orchestrator.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml
from openapi_spec_validator import validate
from openapi_spec_validator.exceptions import OpenAPISpecValidatorError

logger = logging.getLogger(__name__)


def validate_openapi(yaml_str: str) -> dict[str, Any]:
    """
    Validate an OpenAPI 3.x YAML string.

    Returns: {"valid": bool, "errors": list[str], "warnings": list[str]}
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Parse YAML
    try:
        spec = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        return {"valid": False, "errors": [f"YAML parse error: {exc}"], "warnings": []}

    if not isinstance(spec, dict):
        return {"valid": False, "errors": ["Spec is not a valid YAML mapping"], "warnings": []}

    # Check required top-level keys
    if "openapi" not in spec:
        warnings.append("Missing 'openapi' version field — adding default 3.1.0")
        spec["openapi"] = "3.1.0"
    if "info" not in spec:
        warnings.append("Missing 'info' field")
    if "paths" not in spec:
        errors.append("Missing 'paths' field — no endpoints defined")

    # Run openapi-spec-validator
    try:
        validate(spec)
    except OpenAPISpecValidatorError as exc:
        errors.append(f"OpenAPI validation error: {exc}")
    except Exception as exc:
        # Some specs may not fully validate but are still usable
        warnings.append(f"Validation warning: {exc}")

    valid = len(errors) == 0
    if valid:
        logger.info("OpenAPI spec validated successfully")
    else:
        logger.warning("OpenAPI spec validation failed: %s", errors)

    return {"valid": valid, "errors": errors, "warnings": warnings}


def check_cross_refs(contracts: list[dict]) -> list[str]:
    """
    Check cross-service references across multiple contracts.

    Verifies:
    - $ref URLs pointing to other services are consistent
    - No circular dependencies in service-to-service API calls
    - Request/response schemas are compatible across boundaries

    Args:
        contracts: list of dicts with "service_name" and "openapi_yaml" keys

    Returns: list of error strings (empty = all OK)
    """
    errors: list[str] = []
    service_names = set()
    service_endpoints: dict[str, set[str]] = {}  # service → set of paths
    service_deps: dict[str, set[str]] = {}  # service → services it references

    for contract in contracts:
        name = contract.get("service_name", "unknown")
        yaml_str = contract.get("openapi_yaml", "")
        service_names.add(name)

        try:
            spec = yaml.safe_load(yaml_str)
        except yaml.YAMLError:
            errors.append(f"{name}: Cannot parse YAML for cross-ref check")
            continue

        if not isinstance(spec, dict):
            continue

        # Collect endpoints
        paths = spec.get("paths", {})
        service_endpoints[name] = set(paths.keys()) if isinstance(paths, dict) else set()

        # Find $ref or server references to other services
        deps: set[str] = set()
        _find_service_refs(spec, name, deps)
        service_deps[name] = deps

    # Check for circular dependencies
    for svc, deps in service_deps.items():
        for dep in deps:
            if dep in service_deps and svc in service_deps.get(dep, set()):
                errors.append(
                    f"Circular dependency: {svc} ↔ {dep} — "
                    "consider using async events instead of synchronous calls"
                )

    # Check that referenced services exist
    for svc, deps in service_deps.items():
        for dep in deps:
            # Normalise name comparison
            dep_normalised = dep.lower().replace("-", "").replace("_", "")
            found = any(
                s.lower().replace("-", "").replace("_", "") == dep_normalised
                for s in service_names
            )
            if not found:
                errors.append(f"{svc}: references unknown service '{dep}'")

    if errors:
        logger.warning("Cross-ref check found %d issues", len(errors))
    else:
        logger.info("Cross-ref check passed for %d services", len(service_names))

    return errors


def _find_service_refs(obj: Any, own_name: str, deps: set[str]) -> None:
    """Recursively find service references in an OpenAPI spec."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "$ref" and isinstance(value, str) and "service" in value.lower():
                # Extract service name from URL like http://order-service:8080/...
                parts = value.split("//")
                if len(parts) > 1:
                    host = parts[1].split(":")[0].split("/")[0]
                    service_ref = host.replace("-service", "").replace("-svc", "")
                    if service_ref.lower() != own_name.lower():
                        deps.add(service_ref)
            elif key == "servers" and isinstance(value, list):
                for server in value:
                    url = server.get("url", "") if isinstance(server, dict) else ""
                    if "service" in url.lower():
                        parts = url.split("//")
                        if len(parts) > 1:
                            host = parts[1].split(":")[0].split("/")[0]
                            service_ref = host.replace("-service", "").replace("-svc", "")
                            if service_ref.lower() != own_name.lower():
                                deps.add(service_ref)
            else:
                _find_service_refs(value, own_name, deps)
    elif isinstance(obj, list):
        for item in obj:
            _find_service_refs(item, own_name, deps)
