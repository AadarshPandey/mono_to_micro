# backend/api/routes/upload.py
"""
Upload Route — POST /upload
Accepts zip source + optional OTel traces, creates a job, starts pipeline.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile

from backend.api.schemas import JobResponse
from backend.config import settings
from backend.ingestion.job_runner import JOB_STORE, create_job, run_job

router = APIRouter()


@router.post("/upload", response_model=JobResponse, status_code=202)
async def upload(
    background_tasks: BackgroundTasks,
    source_code: UploadFile = File(...),
    otel_traces: UploadFile | None = File(None),
    language: str | None = Form(None),
    hint_services: int | None = Form(None),
) -> JobResponse:
    """Upload monolith source code zip and start the decomposition pipeline."""
    job_id = create_job()

    # Save uploaded zip
    upload_dir = Path(settings.UPLOAD_DIR) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    zip_path = upload_dir / "source.zip"
    with zip_path.open("wb") as f:
        content = await source_code.read()
        f.write(content)

    # Extract zip
    source_dir = upload_dir / "source"
    shutil.unpack_archive(str(zip_path), str(source_dir))

    # Save OTel traces if provided
    otel_path: str | None = None
    if otel_traces is not None:
        otel_file = upload_dir / "otel_traces.json"
        with otel_file.open("wb") as f:
            content = await otel_traces.read()
            f.write(content)
        otel_path = str(otel_file)

    # Start pipeline in background
    background_tasks.add_task(
        run_job,
        job_id=job_id,
        source_path=str(source_dir),
        otel_path=otel_path,
        language=language,
        hint_services=hint_services,
    )

    return JOB_STORE[job_id]
