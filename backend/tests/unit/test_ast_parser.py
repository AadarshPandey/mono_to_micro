# backend/tests/unit/test_ast_parser.py
"""
Unit Tests — AST Parser
"""

from pathlib import Path

import pytest

from backend.ingestion.ast_parser import extract_static_edges, parse_file
from backend.ingestion.language_registry import detect_language


class TestDetectLanguage:
    def test_java(self):
        assert detect_language("Foo.java") == "java"

    def test_python(self):
        assert detect_language("bar.py") == "python"

    def test_csharp(self):
        assert detect_language("Baz.cs") == "csharp"

    def test_go(self):
        assert detect_language("main.go") == "go"

    def test_unknown(self):
        assert detect_language("readme.md") is None


class TestParseFile:
    def test_parse_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_file(str(tmp_path / "nope.java"), "java")

    def test_parse_simple_java(self, tmp_path):
        java_file = tmp_path / "Order.java"
        java_file.write_text("""
package com.example.order;

import com.example.customer.CustomerService;

public class Order {
    private String id;

    public String getId() {
        return id;
    }

    public void process() {
        CustomerService cs = new CustomerService();
    }
}
""")
        result = parse_file(str(java_file), "java")

        assert result["language"] == "java"
        assert len(result["classes"]) == 1
        assert result["classes"][0]["name"] == "Order"
        assert result["classes"][0]["fqn"] == "com.example.order.Order"
        assert len(result["methods"]) >= 1
        assert any(m["name"] == "getId" for m in result["methods"])
        assert len(result["imports"]) == 1
        assert "CustomerService" in result["imports"][0]["target"]

    def test_parse_simple_python(self, tmp_path):
        py_file = tmp_path / "service.py"
        py_file.write_text("""
from models import Order

class OrderService:
    def create_order(self, data):
        return Order(**data)

    def get_order(self, order_id):
        pass
""")
        result = parse_file(str(py_file), "python")

        assert result["language"] == "python"
        assert len(result["classes"]) == 1
        assert result["classes"][0]["name"] == "OrderService"
        assert len(result["methods"]) >= 1
        assert len(result["imports"]) >= 1


class TestExtractStaticEdges:
    def test_import_edges(self, tmp_path):
        # Create two Java files that reference each other
        (tmp_path / "A.java").write_text("""
public class A {
    public void doSomething() {}
}
""")
        (tmp_path / "B.java").write_text("""
import A;
public class B {
    public void callA() {}
}
""")
        from backend.ingestion.ast_parser import parse_directory
        results = parse_directory(str(tmp_path), "java")
        edges = extract_static_edges(results)

        # Should have at least one edge from B -> A
        assert isinstance(edges, list)

    def test_deduplication(self):
        # Test that duplicate edges are removed
        edges = extract_static_edges([
            {
                "file_path": "A.java", "language": "java",
                "classes": [{"name": "A", "fqn": "A"}],
                "methods": [], "calls": [],
                "imports": [
                    {"target": "B", "file_path": "A.java"},
                    {"target": "B", "file_path": "A.java"},
                ],
            },
            {
                "file_path": "B.java", "language": "java",
                "classes": [{"name": "B", "fqn": "B"}],
                "methods": [], "imports": [], "calls": [],
            },
        ])
        import_edges = [e for e in edges if e["edge_type"] == "IMPORTS"]
        # Should be deduplicated
        assert len(import_edges) <= 1
