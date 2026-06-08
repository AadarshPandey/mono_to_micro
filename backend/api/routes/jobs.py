# backend/api/routes/jobs.py
"""
Jobs Route — GET /jobs/{job_id}
Returns current job status for polling.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import JobResponse
from backend.ingestion.job_runner import get_job_status

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Poll job status by ID."""
    job = get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job
