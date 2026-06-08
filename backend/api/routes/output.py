# backend/api/routes/output.py
"""
Output Route — GET /output/{job_id}
Streams the generated zip archive for download.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.api.schemas import JobStatus
from backend.config import settings
from backend.ingestion.job_runner import get_job_status

router = APIRouter()


@router.get("/output/{job_id}")
async def download_output(job_id: str) -> FileResponse:
    """Download the generated microservices archive."""
    job = get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=409, detail=f"Job not complete (status={job.status})")

    zip_path = Path(settings.OUTPUT_DIR) / job_id / f"monolith-breaker-{job_id}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Output archive not found")

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"monolith-breaker-{job_id}.zip",
    )
