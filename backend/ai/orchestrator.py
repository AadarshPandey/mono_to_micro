# backend/ai/orchestrator.py
"""
Orchestrator — LangGraph stateful pipeline definition.

The central pipeline that wires together all ingestion, AI, contract,
and scaffolding steps with human-in-the-loop gates.
Used by job_runner and routes/review.
"""

from __future__ import annotations

import json
import logging

from langgraph.graph import END, StateGraph

from backend.ai.chains.boundary_chain import run_boundary_detection
from backend.ai.chains.code_chain import run_code_extraction
from backend.ai.confidence_scorer import score_all_boundaries
from backend.ai.rag_retriever import retrieve, retrieve_for_boundary, retrieve_for_classes
from backend.api.schemas import (
    BoundaryProposal,
    ContractSpec,
    JobStatus,
    PipelineState,
)
from backend.config import settings
from backend.contracts.asyncapi_generator import generate_asyncapi
from backend.contracts.grpc_generator import generate_proto
from backend.contracts.openapi_generator import generate_openapi
from backend.contracts.validator import check_cross_refs
from backend.db import neo4j_client
from backend.scaffolding.archiver import create_archive
from backend.scaffolding.code_scaffolder import render_service
from backend.scaffolding.infra_generator import generate_all_infra
from backend.scaffolding.strangler_planner import generate_migration_plan

logger = logging.getLogger(__name__)

# ── In-memory pipeline state store (for gate suspend/resume) ───────────────

_pipeline_states: dict[str, PipelineState] = {}


# ── Pipeline node functions ────────────────────────────────────────────────


async def _detect_boundaries(state: PipelineState) -> dict:
    """Node: Use Gemini to propose bounded contexts from graph + RAG."""
    job_id = state["job_id"]
    communities = state.get("neo4j_communities", [])
    language = state.get("language", "java")
    hint = state.get("hint_services")

    _update_job(job_id, JobStatus.AI_PROCESSING, 60, "Detecting service boundaries...")

    # Build graph JSON for the prompt
    graph_json = json.dumps(communities, indent=2)

    # RAG: retrieve most relevant code chunks
    code_chunks = retrieve(f"main classes and services in {language} application", job_id)
    code_text = "\n\n".join(code_chunks) if code_chunks else "(no code context)"

    proposals = await run_boundary_detection(graph_json, code_text, language, hint)

    return {
        "boundary_proposals": [p.model_dump() for p in proposals],
    }


async def _score_confidence(state: PipelineState) -> dict:
    """Node: Score each boundary on cohesion vs coupling."""
    job_id = state["job_id"]
    proposals = state.get("boundary_proposals", [])

    _update_job(job_id, JobStatus.AI_PROCESSING, 65, "Scoring boundary confidence...")

    scores = await score_all_boundaries(proposals, job_id)

    return {
        "confidence_scores": [s.model_dump() for s in scores],
    }


async def _gate_a(state: PipelineState) -> dict:
    """Node: Suspend for human review of service boundaries."""
    job_id = state["job_id"]
    _update_job(job_id, JobStatus.GATE_A, 70, "Waiting for boundary review...")
    # Store state for resume
    _pipeline_states[job_id] = state
    return {}


async def _generate_contracts(state: PipelineState) -> dict:
    """Node: Generate OpenAPI + AsyncAPI + Protobuf for each approved boundary."""
    job_id = state["job_id"]
    boundaries = state.get("approved_boundaries", state.get("boundary_proposals", []))

    _update_job(job_id, JobStatus.CONTRACTING, 75, "Generating API contracts...")

    contracts = []
    for boundary in boundaries:
        # OpenAPI (always)
        spec = await generate_openapi(boundary, job_id)
        contract_dict = spec.model_dump()

        # AsyncAPI (if event-driven)
        asyncapi = await generate_asyncapi(boundary, job_id)
        if asyncapi:
            contract_dict["asyncapi_yaml"] = asyncapi

        # Protobuf (if gRPC)
        proto = await generate_proto(boundary, job_id)
        if proto:
            contract_dict["proto_definition"] = proto

        contracts.append(contract_dict)

    return {"contracts": contracts}


async def _validate_contracts(state: PipelineState) -> dict:
    """Node: Validate generated contracts for consistency."""
    job_id = state["job_id"]
    contracts = state.get("contracts", [])

    _update_job(job_id, JobStatus.CONTRACTING, 78, "Validating contracts...")

    cross_errors = check_cross_refs(contracts)
    if cross_errors:
        logger.warning("Cross-ref errors for job %s: %s", job_id, cross_errors)

    return {}


async def _gate_b(state: PipelineState) -> dict:
    """Node: Suspend for human review of API contracts."""
    job_id = state["job_id"]
    _update_job(job_id, JobStatus.GATE_B, 80, "Waiting for contract review...")
    _pipeline_states[job_id] = state
    return {}


async def _generate_code(state: PipelineState) -> dict:
    """Node: Use Gemini to extract and rewrite service code."""
    job_id = state["job_id"]
    boundaries = state.get("approved_boundaries", state.get("boundary_proposals", []))
    contracts = state.get("approved_contracts", state.get("contracts", []))
    language = state.get("language", "java")

    _update_job(job_id, JobStatus.SCAFFOLDING, 82, "Generating service code...")

    framework = "springboot" if language == "java" else "fastapi"
    scaffolded = []

    for i, boundary in enumerate(boundaries):
        b_name = boundary.get("name", f"Service{i}")
        b_classes = boundary.get("classes", [])

        # Find matching contract
        contract_yaml = ""
        for c in contracts:
            if c.get("service_name", "") == b_name:
                contract_yaml = c.get("openapi_yaml", "")
                break

        # Get source code for these classes
        source_code = retrieve_for_classes(b_classes, job_id)

        # Generate code via LLM
        result = await run_code_extraction(
            service_name=b_name,
            openapi_spec=contract_yaml,
            source_classes=source_code,
            language=language,
            framework=framework,
        )

        scaffolded.append({
            "service_name": b_name,
            "files": result.get("files", []),
        })

    return {"scaffolded_services": scaffolded}


async def _generate_infra(state: PipelineState) -> dict:
    """Node: Render Dockerfile, K8s YAML, compose block for each service."""
    job_id = state["job_id"]
    scaffolded = state.get("scaffolded_services", [])
    boundaries = state.get("approved_boundaries", state.get("boundary_proposals", []))
    language = state.get("language", "java")

    _update_job(job_id, JobStatus.SCAFFOLDING, 88, "Generating infrastructure files...")

    port = 8081
    for i, svc in enumerate(scaffolded):
        svc_name = svc.get("service_name", f"Service{i}")
        deps = []
        for b in boundaries:
            if b.get("name") == svc_name:
                deps = b.get("dependencies_on", [])
                break

        # Render code templates + merge LLM files
        render_service(
            service_name=svc_name,
            language=language,
            generated_files=svc.get("files", []),
            openapi_spec="",
            dependencies=deps,
            job_id=job_id,
        )

        # Generate infra
        generate_all_infra(
            service_name=svc_name,
            language=language,
            port=port,
            dependencies=deps,
            job_id=job_id,
        )
        port += 1

    return {}


async def _generate_migration(state: PipelineState) -> dict:
    """Node: Generate strangler-fig facade + phased migration plan."""
    job_id = state["job_id"]
    boundaries = state.get("approved_boundaries", state.get("boundary_proposals", []))
    contracts = state.get("approved_contracts", state.get("contracts", []))

    _update_job(job_id, JobStatus.SCAFFOLDING, 92, "Generating migration plans...")

    for boundary in boundaries:
        b_name = boundary.get("name", "")
        contract_yaml = ""
        for c in contracts:
            if c.get("service_name", "") == b_name:
                contract_yaml = c.get("openapi_yaml", "")
                break

        await generate_migration_plan(
            service_name=b_name,
            boundary=boundary,
            openapi_spec=contract_yaml,
            job_id=job_id,
        )

    return {}


async def _package_output(state: PipelineState) -> dict:
    """Node: Zip all artefacts and mark job as done."""
    job_id = state["job_id"]
    _update_job(job_id, JobStatus.SCAFFOLDING, 96, "Packaging output archive...")

    zip_path = create_archive(job_id)
    _update_job(job_id, JobStatus.DONE, 100, "Complete — download ready")

    return {"output_zip_path": zip_path}


# ── Pipeline builder ───────────────────────────────────────────────────────


def build_pipeline() -> StateGraph:
    """Build the LangGraph StateGraph with all nodes and edges."""
    graph = StateGraph(PipelineState)

    # Register nodes
    graph.add_node("detect_boundaries", _detect_boundaries)
    graph.add_node("score_confidence", _score_confidence)
    graph.add_node("gate_a", _gate_a)
    graph.add_node("generate_contracts", _generate_contracts)
    graph.add_node("validate_contracts", _validate_contracts)
    graph.add_node("gate_b", _gate_b)
    graph.add_node("generate_code", _generate_code)
    graph.add_node("generate_infra", _generate_infra)
    graph.add_node("generate_migration", _generate_migration)
    graph.add_node("package_output", _package_output)

    # Define edges (pipeline order)
    graph.set_entry_point("detect_boundaries")
    graph.add_edge("detect_boundaries", "score_confidence")
    graph.add_edge("score_confidence", "gate_a")
    graph.add_edge("gate_a", "generate_contracts")
    graph.add_edge("generate_contracts", "validate_contracts")
    graph.add_edge("validate_contracts", "gate_b")
    graph.add_edge("gate_b", "generate_code")
    graph.add_edge("generate_code", "generate_infra")
    graph.add_edge("generate_infra", "generate_migration")
    graph.add_edge("generate_migration", "package_output")
    graph.add_edge("package_output", END)

    return graph


# ── Public API ─────────────────────────────────────────────────────────────


async def run_pipeline(
    job_id: str,
    source_path: str,
    otel_path: str | None,
    language: str,
    hint_services: int | None = None,
    ast_results: list[dict] | None = None,
    static_edges: list[dict] | None = None,
    dynamic_edges: list[dict] | None = None,
    communities: list[dict] | None = None,
) -> None:
    """
    Run the AI pipeline from boundary detection through Gate A suspension.

    Called by job_runner after ingestion is complete.
    Executes steps sequentially and suspends at Gate A for human review.
    Gate B suspension happens inside resume_from_gate("gate_a", ...).
    """
    state: PipelineState = {
        "job_id": job_id,
        "source_path": source_path,
        "otel_path": otel_path,
        "language": language,
        "hint_services": hint_services,
        "ast_nodes": ast_results or [],
        "static_edges": static_edges or [],
        "dynamic_edges": dynamic_edges or [],
        "neo4j_communities": communities or [],
        "boundary_proposals": [],
        "confidence_scores": [],
        "gate_a_approved": False,
        "approved_boundaries": [],
        "contracts": [],
        "gate_b_approved": False,
        "approved_contracts": [],
        "scaffolded_services": [],
        "output_zip_path": "",
        "error": None,
    }

    try:
        # Step 1: Detect boundaries
        updates = await _detect_boundaries(state)
        state.update(updates)

        # Step 2: Score confidence
        updates = await _score_confidence(state)
        state.update(updates)

        # Step 3: Suspend at Gate A for human review
        await _gate_a(state)
        _pipeline_states[job_id] = state
        logger.info("Pipeline suspended at Gate A for job %s", job_id)

    except Exception as exc:
        logger.exception("Pipeline failed for job %s: %s", job_id, exc)
        _update_job(job_id, JobStatus.ERROR, 0, "Pipeline failed", str(exc))



async def resume_from_gate(
    job_id: str,
    gate: str,
    approved_data: dict,
) -> None:
    """
    Resume the pipeline after a human gate approval.

    Args:
        job_id: The job to resume
        gate: "gate_a" or "gate_b"
        approved_data: Contains approved/modified boundaries or contracts
    """
    state = _pipeline_states.get(job_id)
    if state is None:
        raise ValueError(f"No suspended pipeline found for job {job_id}")

    if gate == "gate_a":
        boundaries = approved_data.get("boundaries", state.get("boundary_proposals", []))
        state["gate_a_approved"] = True
        state["approved_boundaries"] = boundaries


        # Continue from generate_contracts

        try:
            # Run remaining nodes sequentially
            # Generate contracts
            updates = await _generate_contracts(state)
            state.update(updates)

            # Validate contracts
            updates = await _validate_contracts(state)
            state.update(updates)

            # Suspend at Gate B
            await _gate_b(state)
            _pipeline_states[job_id] = state
            logger.info("Pipeline suspended at Gate B for job %s", job_id)

        except Exception as exc:
            logger.exception("Pipeline failed after Gate A for job %s: %s", job_id, exc)
            _update_job(job_id, JobStatus.ERROR, 0, "Pipeline failed after Gate A", str(exc))

    elif gate == "gate_b":
        contracts = approved_data.get("contracts", state.get("contracts", []))
        state["gate_b_approved"] = True
        state["approved_contracts"] = contracts

        try:
            # Generate code
            updates = await _generate_code(state)
            state.update(updates)

            # Generate infra
            updates = await _generate_infra(state)
            state.update(updates)

            # Generate migration plans
            updates = await _generate_migration(state)
            state.update(updates)

            # Package output
            updates = await _package_output(state)
            state.update(updates)

            # Clean up stored state
            _pipeline_states.pop(job_id, None)

        except Exception as exc:
            logger.exception("Pipeline failed after Gate B for job %s: %s", job_id, exc)
            _update_job(job_id, JobStatus.ERROR, 0, "Pipeline failed after Gate B", str(exc))

    else:
        raise ValueError(f"Unknown gate: {gate}")


# ── Helpers ────────────────────────────────────────────────────────────────


def _update_job(
    job_id: str,
    status: JobStatus,
    progress: int,
    step: str,
    error: str | None = None,
) -> None:
    """Update job status via job_runner (avoids circular import)."""
    from backend.ingestion.job_runner import update_job_status
    update_job_status(job_id, status, progress, step, error)


def get_pipeline_state(job_id: str) -> PipelineState | None:
    """Get the suspended pipeline state for a job (used by review routes)."""
    return _pipeline_states.get(job_id)
