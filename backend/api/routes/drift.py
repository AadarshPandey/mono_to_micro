# backend/api/routes/drift.py
"""
Drift Routes — POST /drift/scan and GET /drift/alerts
Post-deployment drift detection endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.api.schemas import DriftAlert, DriftScanRequest
from backend.drift.alerter import write_alerts, fire_webhook
from backend.drift.detector import detect_violations
from backend.drift.scanner import scan_service_repo

router = APIRouter()


async def _run_drift_scan(job_id: str, service_repo_path: str) -> None:
    """Background task: run full drift scan pipeline."""
    current_graph = scan_service_repo(service_repo_path)
    violations = await detect_violations(current_graph, job_id)
    if violations:
        await write_alerts(violations)
        await fire_webhook(violations)


@router.post("/drift/scan", status_code=202)
async def trigger_drift_scan(
    request: DriftScanRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Trigger a drift detection scan on a deployed service repo."""
    background_tasks.add_task(_run_drift_scan, request.job_id, request.service_repo_path)
    return {"job_id": request.job_id, "status": "scan_started"}


@router.get("/drift/alerts")
async def get_drift_alerts(job_id: str) -> dict:
    """Get drift alerts for a job."""
    from backend.db import neo4j_client

    records = await neo4j_client.run_query(
        """
        MATCH (d:DriftAlert {job_id: $job_id})
        RETURN d.id AS id, d.job_id AS job_id, d.service_name AS service_name,
               d.violation_type AS violation_type, d.detected_at AS detected_at,
               d.resolved AS resolved
        ORDER BY d.detected_at DESC
        """,
        {"job_id": job_id},
    )

    return {"alerts": records}
