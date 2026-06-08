# backend/tests/integration/test_drift_scanner.py
"""
Integration Tests — Drift scanner

FUTURE DEVELOPMENT:
- Requires running Neo4j instance with seeded boundary graph.
- Test scanning a service repo that has no drift → expect 0 alerts.
- Test scanning a repo with intentional circular dependency → expect CIRCULAR_DEP alert.
- Test scanning a repo with cross-boundary import → expect CROSS_BOUNDARY_CALL alert.
- Verify DriftAlert nodes are created in Neo4j.
- Verify webhook is called if DRIFT_WEBHOOK_URL is configured (mock).
"""
