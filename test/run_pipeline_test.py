"""
End-to-End Pipeline Test — Runs the full Monolith Breaker pipeline locally.

Usage:
    cd /home/aadarsh/Documents/mono_to_micro
    uv run python test/run_pipeline_test.py

Reads the Gemini API key from .env, uses test/legacy-monolith.zip as input,
and outputs decomposed microservices to test/output/.
Skips human gates (auto-approves boundaries and contracts).
"""

import asyncio
import json
import logging
import os
import shutil
import sys
import zipfile
from pathlib import Path

# ── Ensure project root is on sys.path ─────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# ── Setup logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("pipeline_test")

# ── Override OUTPUT_DIR BEFORE importing backend ──────────────────────────
# This makes all pipeline output go to test/output/ instead of data/outputs/
os.environ["OUTPUT_DIR"] = str(PROJECT_ROOT / "test" / "output")


async def main():
    """Run the full decomposition pipeline end-to-end."""

    # ── 1. Validate prerequisites ──────────────────────────────────────
    from backend.config import settings

    zip_path = PROJECT_ROOT / "test" / "legacy-monolith.zip"
    if not zip_path.exists():
        logger.error("❌ Source zip not found: %s", zip_path)
        logger.info("Run: cd test/legacy-monolith && zip -r ../legacy-monolith.zip src/ pom.xml")
        sys.exit(1)

    if not settings.GOOGLE_API_KEY:
        logger.error("❌ GOOGLE_API_KEY is empty in .env")
        sys.exit(1)

    logger.info("✅ API key found: %s...", settings.GOOGLE_API_KEY[:10])
    logger.info("✅ Model: %s", settings.GEMINI_MODEL)
    logger.info("✅ Source zip: %s", zip_path)
    logger.info("✅ Output dir: %s", settings.OUTPUT_DIR)

    # ── 2. Extract the zip ────────────────────────────────────────────
    extract_dir = PROJECT_ROOT / "test" / "_extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # Find Java source root
    source_path = str(extract_dir)
    logger.info("✅ Extracted to: %s", source_path)

    # ── 3. Ensure output dir exists ───────────────────────────────────
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

    # ── 4. Run the ingestion pipeline (parse → graph → embed) ─────────
    from backend.ingestion.ast_parser import extract_static_edges, parse_directory
    from backend.ingestion.dynamic_analyzer import parse_otel_traces
    from backend.ingestion.embedder import embed_and_store, update_community_ids
    from backend.ingestion.graph_builder import build_graph

    job_id = "test-pipeline-run"

    logger.info("=" * 60)
    logger.info("STEP 1: Parsing AST with Tree-sitter...")
    logger.info("=" * 60)
    ast_results = parse_directory(source_path, "java")
    static_edges = extract_static_edges(ast_results)
    logger.info("  Parsed %d files, %d static edges", len(ast_results), len(static_edges))

    if not ast_results:
        logger.error("❌ No Java files found. Check zip structure.")
        sys.exit(1)

    # Print what was parsed
    for r in ast_results:
        logger.info("  📄 %s: %d classes, %d methods",
                     r.get("file", "?"),
                     len(r.get("classes", [])),
                     len(r.get("methods", [])))

    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 2: Dynamic analysis (no OTel traces)...")
    logger.info("=" * 60)
    dynamic_edges = parse_otel_traces(None)
    logger.info("  %d dynamic edges (none expected without OTel)", len(dynamic_edges))

    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 3: Building Neo4j graph + Louvain clustering...")
    logger.info("=" * 60)
    try:
        communities = await build_graph(ast_results, static_edges, dynamic_edges, job_id, "java")
        logger.info("  %d communities detected", len(communities))
        for c in communities:
            logger.info("  🏘️  Community %s: %s", c.get("id", "?"), c.get("classes", []))
    except Exception as exc:
        logger.warning("⚠️  Neo4j graph build failed (is Neo4j running?): %s", exc)
        logger.info("  Falling back to simple community detection from AST...")
        # Build fallback communities from class packages
        communities = _build_fallback_communities(ast_results)
        logger.info("  %d fallback communities", len(communities))

    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 4: Embedding code into ChromaDB...")
    logger.info("=" * 60)
    try:
        num_chunks = embed_and_store(ast_results, source_path, job_id)
        logger.info("  Embedded %d chunks", num_chunks)
    except Exception as exc:
        logger.warning("⚠️  Embedding failed: %s", exc)
        logger.info("  Pipeline will continue with limited RAG context")

    # ── 5. Run AI boundary detection ──────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 5: AI Boundary Detection (Gemini)...")
    logger.info("=" * 60)

    from backend.ai.chains.boundary_chain import run_boundary_detection
    from backend.ai.rag_retriever import retrieve

    graph_json = json.dumps(communities, indent=2)
    try:
        code_chunks = retrieve("main classes and services in java application", job_id)
        code_text = "\n\n".join(code_chunks) if code_chunks else "(no code context)"
    except Exception:
        code_text = "(no code context — ChromaDB unavailable)"

    proposals = await run_boundary_detection(graph_json, code_text, "java", num_services_hint=None)
    logger.info("  🎯 %d boundary proposals:", len(proposals))
    for p in proposals:
        logger.info("    → %s: classes=%s", p.name, p.classes)

    # ── 6. Auto-approve boundaries (skip Gate A) ──────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 6: Auto-approving boundaries (skipping Gate A)...")
    logger.info("=" * 60)
    approved_boundaries = [p.model_dump() for p in proposals]
    logger.info("  Approved %d boundaries", len(approved_boundaries))

    # ── 7. Generate contracts ─────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 7: Generating API contracts...")
    logger.info("=" * 60)

    from backend.contracts.openapi_generator import generate_openapi
    from backend.contracts.asyncapi_generator import generate_asyncapi
    from backend.contracts.grpc_generator import generate_proto

    contracts = []
    for boundary in approved_boundaries:
        b_name = boundary.get("name", "Unknown")
        logger.info("  📜 Generating contracts for: %s", b_name)

        spec = await generate_openapi(boundary, job_id)
        contract_dict = spec.model_dump()

        try:
            asyncapi = await generate_asyncapi(boundary, job_id)
            if asyncapi:
                contract_dict["asyncapi_yaml"] = asyncapi
        except Exception as exc:
            logger.warning("    AsyncAPI skipped: %s", exc)

        try:
            proto = await generate_proto(boundary, job_id)
            if proto:
                contract_dict["proto_definition"] = proto
        except Exception as exc:
            logger.warning("    Proto skipped: %s", exc)

        contracts.append(contract_dict)

    logger.info("  Generated %d contract specs", len(contracts))

    # ── 8. Auto-approve contracts (skip Gate B) ───────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 8: Auto-approving contracts (skipping Gate B)...")
    logger.info("=" * 60)
    approved_contracts = contracts

    # ── 9. Generate service code ──────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 9: Generating microservice code...")
    logger.info("=" * 60)

    from backend.ai.chains.code_chain import run_code_extraction

    scaffolded_services = []
    for i, boundary in enumerate(approved_boundaries):
        b_name = boundary.get("name", f"Service{i}")
        b_classes = boundary.get("classes", [])
        logger.info("  🏗️  Generating code for: %s", b_name)

        # Find matching contract
        contract_yaml = ""
        for c in approved_contracts:
            if c.get("service_name", "") == b_name:
                contract_yaml = c.get("openapi_yaml", "")
                break

        # Get source code for these classes
        try:
            from backend.ai.rag_retriever import retrieve_for_classes
            source_code = retrieve_for_classes(b_classes, job_id)
        except Exception:
            source_code = "(source code unavailable)"

        result = await run_code_extraction(
            service_name=b_name,
            openapi_spec=contract_yaml,
            source_classes=source_code,
            language="java",
            framework="springboot",
        )
        scaffolded_services.append({
            "service_name": b_name,
            "files": result.get("files", []),
        })

    # ── 10. Generate infra + scaffolding ──────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 10: Scaffolding + Infrastructure generation...")
    logger.info("=" * 60)

    from backend.scaffolding.code_scaffolder import render_service, reset_port_counter
    from backend.scaffolding.infra_generator import generate_all_infra

    reset_port_counter()
    port = 8081
    for i, svc in enumerate(scaffolded_services):
        svc_name = svc.get("service_name", f"Service{i}")
        deps = []
        for b in approved_boundaries:
            if b.get("name") == svc_name:
                deps = b.get("dependencies_on", [])
                break

        render_service(
            service_name=svc_name,
            language="java",
            generated_files=svc.get("files", []),
            openapi_spec="",
            dependencies=deps,
            job_id=job_id,
        )
        generate_all_infra(
            service_name=svc_name,
            language="java",
            port=port,
            dependencies=deps,
            job_id=job_id,
        )
        logger.info("  ✅ %s scaffolded at port %d", svc_name, port)
        port += 1

    # ── 11. Generate migration plans ──────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 11: Generating strangler-fig migration plans...")
    logger.info("=" * 60)

    from backend.scaffolding.strangler_planner import generate_migration_plan

    for boundary in approved_boundaries:
        b_name = boundary.get("name", "")
        contract_yaml = ""
        for c in approved_contracts:
            if c.get("service_name", "") == b_name:
                contract_yaml = c.get("openapi_yaml", "")
                break

        await generate_migration_plan(
            service_name=b_name,
            boundary=boundary,
            openapi_spec=contract_yaml,
            job_id=job_id,
        )
        logger.info("  ✅ Migration plan for: %s", b_name)

    # ── 12. Package archive ───────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 12: Packaging output archive...")
    logger.info("=" * 60)

    from backend.scaffolding.archiver import create_archive

    zip_output = create_archive(job_id)
    logger.info("  📦 Archive created: %s", zip_output)

    # ── Done! ─────────────────────────────────────────────────────────
    output_dir = Path(settings.OUTPUT_DIR) / job_id
    logger.info("")
    logger.info("=" * 60)
    logger.info("🎉 PIPELINE COMPLETE!")
    logger.info("=" * 60)
    logger.info("  Output directory: %s", output_dir)
    logger.info("  Archive: %s", zip_output)
    logger.info("")

    # List what was generated
    logger.info("Generated files:")
    for f in sorted(output_dir.rglob("*")):
        if f.is_file() and not f.name.endswith(".zip"):
            logger.info("  📄 %s", f.relative_to(output_dir))

    # Cleanup extracted source
    shutil.rmtree(extract_dir, ignore_errors=True)


def _build_fallback_communities(ast_results: list[dict]) -> list[dict]:
    """Build simple communities from AST classes when Neo4j is unavailable."""
    from collections import defaultdict
    packages = defaultdict(list)

    for result in ast_results:
        for cls in result.get("classes", []):
            fqn = cls.get("fqn", cls.get("name", ""))
            parts = fqn.rsplit(".", 1)
            package = parts[0] if len(parts) > 1 else "default"
            packages[package].append(fqn)

    communities = []
    for i, (pkg, classes) in enumerate(packages.items()):
        communities.append({
            "id": i,
            "classes": classes,
            "package": pkg,
        })
    return communities


if __name__ == "__main__":
    asyncio.run(main())
