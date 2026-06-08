# backend/tests/unit/test_contract_validator.py
"""
Unit Tests — Contract Validator
"""

import pytest

from backend.contracts.validator import validate_openapi, check_cross_refs


class TestValidateOpenapi:
    def test_valid_spec(self):
        spec = """
openapi: "3.1.0"
info:
  title: Test Service
  version: "1.0.0"
paths:
  /health:
    get:
      summary: Health check
      responses:
        "200":
          description: OK
"""
        result = validate_openapi(spec)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_missing_paths(self):
        spec = """
openapi: "3.1.0"
info:
  title: Test
  version: "1.0"
"""
        result = validate_openapi(spec)
        # Missing paths should generate an error
        assert "paths" in str(result["errors"]).lower() or len(result["warnings"]) > 0

    def test_invalid_yaml(self):
        result = validate_openapi("not: valid: yaml: {{{}}")
        assert result["valid"] is False

    def test_non_mapping_yaml(self):
        result = validate_openapi("- just\n- a\n- list")
        assert result["valid"] is False
        assert any("mapping" in e.lower() for e in result["errors"])


class TestCheckCrossRefs:
    def test_no_contracts(self):
        errors = check_cross_refs([])
        assert errors == []

    def test_no_cross_refs(self):
        contracts = [
            {"service_name": "Order", "openapi_yaml": "openapi: '3.1.0'\ninfo:\n  title: Order\n  version: '1.0'\npaths: {}"},
            {"service_name": "Customer", "openapi_yaml": "openapi: '3.1.0'\ninfo:\n  title: Customer\n  version: '1.0'\npaths: {}"},
        ]
        errors = check_cross_refs(contracts)
        assert errors == []

    def test_circular_dependency_detected(self):
        contracts = [
            {
                "service_name": "order",
                "openapi_yaml": """
openapi: "3.1.0"
info: {title: Order, version: "1.0"}
paths: {}
servers:
  - url: http://customer-service:8080
""",
            },
            {
                "service_name": "customer",
                "openapi_yaml": """
openapi: "3.1.0"
info: {title: Customer, version: "1.0"}
paths: {}
servers:
  - url: http://order-service:8080
""",
            },
        ]
        errors = check_cross_refs(contracts)
        # Should detect circular dependency between order and customer
        assert len(errors) >= 1
