# backend/tests/integration/test_pipeline_e2e.py
"""
Integration Tests — End-to-end pipeline test

FUTURE DEVELOPMENT:
- Requires running Neo4j and ChromaDB instances.
- Upload the sample_monolith fixture via the /upload API.
- Verify each pipeline step completes: parsing → graphing → embedding → AI → scaffolding.
- Auto-approve Gate A and Gate B with fixture data.
- Verify output zip contains expected service directories and files.
- Verify Neo4j contains expected Class, Method, BoundedContext nodes.
- Verify ChromaDB contains embedded code chunks with correct metadata.
"""
