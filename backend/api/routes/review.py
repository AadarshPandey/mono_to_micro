# backend/api/routes/review.py
"""
Review Routes — Gate A (Boundaries) and Gate B (Contracts).
Human-in-the-loop approval endpoints that resume the pipeline.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.ai.orchestrator import get_pipeline_state, resume_from_gate
from backend.api.schemas import (
    BoundaryReviewRequest,
    ContractReviewRequest,
    JobResponse,
    JobStatus,
)
from backend.ingestion.job_runner import JOB_STORE, get_job_status

router = APIRouter()


@router.post("/review/boundaries", response_model=JobResponse)
async def review_boundaries(
    request: BoundaryReviewRequest,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    """Gate A — Approve or reject proposed service boundaries."""
    job = get_job_status(request.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.GATE_A:
        raise HTTPException(status_code=409, detail=f"Job is not at Gate A (status={job.status})")

    state = get_pipeline_state(request.job_id)
    if state is None:
        raise HTTPException(status_code=409, detail="No suspended pipeline state found")

    if request.decision == "approved":
        # Use modified boundaries if provided, otherwise use AI proposals
        approved = None
        if request.boundaries:
            approved = [b.model_dump() for b in request.boundaries]

        # Run gate resume in background so the HTTP response returns immediately
        background_tasks.add_task(
            _run_gate_resume,
            job_id=request.job_id,
            gate="gate_a",
            approved_data={"boundaries": approved} if approved else {},
        )
    else:
        # Rejection — keep at gate_a for re-review
        pass

    return get_job_status(request.job_id)  # type: ignore


@router.post("/review/contracts", response_model=JobResponse)
async def review_contracts(
    request: ContractReviewRequest,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    """Gate B — Approve or reject generated API contracts."""
    job = get_job_status(request.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.GATE_B:
        raise HTTPException(status_code=409, detail=f"Job is not at Gate B (status={job.status})")

    state = get_pipeline_state(request.job_id)
    if state is None:
        raise HTTPException(status_code=409, detail="No suspended pipeline state found")

    if request.decision == "approved":
        approved = None
        if request.contracts:
            approved = [c.model_dump() for c in request.contracts]

        # Run gate resume in background — code gen can take several minutes
        background_tasks.add_task(
            _run_gate_resume,
            job_id=request.job_id,
            gate="gate_b",
            approved_data={"contracts": approved} if approved else {},
        )

    return get_job_status(request.job_id)  # type: ignore


@router.get("/review/boundaries/{job_id}")
async def get_boundary_proposals(job_id: str) -> dict:
    """Get the current boundary proposals for Gate A review."""
    state = get_pipeline_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No pipeline state found")
    return {
        "job_id": job_id,
        "boundary_proposals": state.get("boundary_proposals", []),
        "confidence_scores": state.get("confidence_scores", []),
    }


@router.get("/review/contracts/{job_id}")
async def get_contract_specs(job_id: str) -> dict:
    """Get the generated contracts for Gate B review."""
    state = get_pipeline_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No pipeline state found")
    return {
        "job_id": job_id,
        "contracts": state.get("contracts", []),
    }


# ── Helper to run async gate resume from background task ───────────────────

async def _run_gate_resume(job_id: str, gate: str, approved_data: dict) -> None:
    """Wrapper to run resume_from_gate in a background task."""
    await resume_from_gate(
        job_id=job_id,
        gate=gate,
        approved_data=approved_data,
    )
