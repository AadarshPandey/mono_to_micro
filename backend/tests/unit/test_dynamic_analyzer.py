# backend/tests/unit/test_dynamic_analyzer.py
"""
Unit Tests — Dynamic Analyzer
"""

import json

import pytest

from backend.ingestion.dynamic_analyzer import parse_otel_traces


class TestParseOtelTraces:
    def test_none_path_returns_empty(self):
        result = parse_otel_traces(None)
        assert result == []

    def test_missing_file_returns_empty(self):
        result = parse_otel_traces("/nonexistent/file.json")
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        result = parse_otel_traces(str(f))
        assert result == []

    def test_malformed_json_returns_empty(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json")
        result = parse_otel_traces(str(f))
        assert result == []

    def test_empty_resource_spans(self, tmp_path):
        f = tmp_path / "empty_spans.json"
        f.write_text(json.dumps({"resourceSpans": []}))
        result = parse_otel_traces(str(f))
        assert result == []

    def test_valid_traces_with_attributes(self, tmp_path):
        traces = {
            "resourceSpans": [{
                "scopeSpans": [{
                    "spans": [
                        {
                            "name": "OrderService.createOrder",
                            "startTimeUnixNano": "1000000000",
                            "endTimeUnixNano": "1050000000",
                            "attributes": [
                                {"key": "code.namespace", "value": {"stringValue": "OrderService"}},
                                {"key": "peer.service", "value": {"stringValue": "CustomerService"}},
                            ],
                        },
                        {
                            "name": "OrderService.createOrder",
                            "startTimeUnixNano": "2000000000",
                            "endTimeUnixNano": "2030000000",
                            "attributes": [
                                {"key": "code.namespace", "value": {"stringValue": "OrderService"}},
                                {"key": "peer.service", "value": {"stringValue": "CustomerService"}},
                            ],
                        },
                    ],
                }],
            }],
        }
        f = tmp_path / "traces.json"
        f.write_text(json.dumps(traces))

        result = parse_otel_traces(str(f))
        assert len(result) >= 1

        edge = result[0]
        assert "source_fqn" in edge
        assert "target_fqn" in edge
        assert "call_count" in edge
        assert edge["call_count"] >= 1
        assert 0.0 <= edge["dynamic_weight"] <= 1.0
        assert edge["latency_p99_ms"] >= 0

    def test_normalisation(self, tmp_path):
        """dynamic_weight should be normalised to 0.0-1.0."""
        traces = {
            "resourceSpans": [{
                "scopeSpans": [{
                    "spans": [
                        {
                            "name": "A.method",
                            "startTimeUnixNano": "1000000000",
                            "endTimeUnixNano": "1010000000",
                            "attributes": [
                                {"key": "code.namespace", "value": {"stringValue": "A"}},
                                {"key": "peer.service", "value": {"stringValue": "B"}},
                            ],
                        },
                    ] * 10 + [
                        {
                            "name": "C.method",
                            "startTimeUnixNano": "1000000000",
                            "endTimeUnixNano": "1010000000",
                            "attributes": [
                                {"key": "code.namespace", "value": {"stringValue": "C"}},
                                {"key": "peer.service", "value": {"stringValue": "D"}},
                            ],
                        },
                    ] * 2,
                }],
            }],
        }
        f = tmp_path / "multi.json"
        f.write_text(json.dumps(traces))

        result = parse_otel_traces(str(f))
        weights = [e["dynamic_weight"] for e in result]
        assert max(weights) == 1.0  # highest count normalised to 1.0
        assert all(0.0 <= w <= 1.0 for w in weights)
