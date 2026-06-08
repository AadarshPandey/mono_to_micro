# backend/api/schemas.py
"""
API Schemas — All Pydantic request/response models and LangGraph state.

Pure data models with no external dependencies. Used by routes, orchestrator,
chains, and scorers across the entire project.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────


class JobStatus(str, Enum):
    QUEUED = "queued"
    PARSING = "parsing"
    GRAPHING = "graphing"
    EMBEDDING = "embedding"
    AI_PROCESSING = "ai_processing"
    GATE_A = "gate_a"
    CONTRACTING = "contracting"
    GATE_B = "gate_b"
    SCAFFOLDING = "scaffolding"
    DONE = "done"
    ERROR = "error"


class ApiStyle(str, Enum):
    REST = "REST"
    GRPC = "gRPC"
    EVENT_DRIVEN = "event-driven"


class ViolationType(str, Enum):
    CIRCULAR_DEP = "CIRCULAR_DEP"
    SHARED_DB = "SHARED_DB"
    CROSS_BOUNDARY_CALL = "CROSS_BOUNDARY_CALL"
    GOD_CLASS_REGROWTH = "GOD_CLASS_REGROWTH"


# ── Request Models ─────────────────────────────────────────────────────────


class UploadRequest(BaseModel):
    language: str | None = None
    hint_services: int | None = None


class BoundaryOverride(BaseModel):
    name: str
    classes: list[str]
    api_style: ApiStyle = ApiStyle.REST


class BoundaryReviewRequest(BaseModel):
    job_id: str
    decision: str  # "approved" | "rejected"
    boundaries: list[BoundaryOverride] | None = None


class ContractOverride(BaseModel):
    service_name: str
    openapi_yaml: str


class ContractReviewRequest(BaseModel):
    job_id: str
    decision: str  # "approved" | "rejected"
    contracts: list[ContractOverride] | None = None


class DriftScanRequest(BaseModel):
    job_id: str
    service_repo_path: str


# ── Response Models ────────────────────────────────────────────────────────


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    current_step: str = ""
    error: str | None = None


class BoundaryProposal(BaseModel):
    name: str
    classes: list[str]
    rationale: str = ""
    suggested_api_style: str = "REST"
    dependencies_on: list[str] = Field(default_factory=list)


class ConfidenceScore(BaseModel):
    boundary_name: str
    cohesion: float = 0.0
    coupling: float = 0.0
    confidence: float = 0.0
    flagged: bool = False


class ContractSpec(BaseModel):
    service_name: str
    openapi_yaml: str = ""
    asyncapi_yaml: str | None = None
    proto_definition: str | None = None


class GeneratedFile(BaseModel):
    path: str
    content: str


class ScaffoldedService(BaseModel):
    service_name: str
    files: list[GeneratedFile] = Field(default_factory=list)


class DriftAlert(BaseModel):
    id: str
    job_id: str
    service_name: str
    violation_type: ViolationType
    detected_at: datetime
    resolved: bool = False


# ── LangGraph Pipeline State ──────────────────────────────────────────────


class PipelineState(TypedDict, total=False):
    """Full state schema for the LangGraph stateful pipeline."""

    job_id: str
    source_path: str
    otel_path: str | None
    language: str
    hint_services: int | None

    # Ingestion outputs
    ast_nodes: list[dict]
    static_edges: list[dict]
    dynamic_edges: list[dict]
    neo4j_communities: list[dict]

    # AI outputs
    boundary_proposals: list[dict]
    confidence_scores: list[dict]

    # Gate A
    gate_a_approved: bool
    approved_boundaries: list[dict]

    # Contract outputs
    contracts: list[dict]

    # Gate B
    gate_b_approved: bool
    approved_contracts: list[dict]

    # Scaffolding outputs
    scaffolded_services: list[dict]
    output_zip_path: str

    # Error tracking
    error: str | None
