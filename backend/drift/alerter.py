# backend/drift/alerter.py
"""
Drift Alerter — Writes DriftAlert nodes to Neo4j and fires webhooks.

Persists alerts and optionally notifies external systems.
Used by routes/drift and scripts/drift_cron.
"""

from __future__ import annotations

import logging

import httpx

from backend.api.schemas import DriftAlert
from backend.config import settings
from backend.db import neo4j_client

logger = logging.getLogger(__name__)


async def write_alerts(alerts: list[DriftAlert]) -> None:
    """Write drift alert nodes to Neo4j."""
    for alert in alerts:
        await neo4j_client.run_write(
            """
            CREATE (d:DriftAlert {
                id: $id,
                job_id: $job_id,
                service_name: $service_name,
                violation_type: $violation_type,
                detected_at: $detected_at,
                resolved: false
            })
            """,
            {
                "id": alert.id,
                "job_id": alert.job_id,
                "service_name": alert.service_name,
                "violation_type": alert.violation_type.value,
                "detected_at": alert.detected_at.isoformat(),
            },
        )
    logger.info("Wrote %d drift alerts to Neo4j", len(alerts))


async def resolve_alert(alert_id: str) -> None:
    """Mark a drift alert as resolved in Neo4j."""
    await neo4j_client.run_write(
        "MATCH (d:DriftAlert {id: $id}) SET d.resolved = true",
        {"id": alert_id},
    )
    logger.info("Resolved drift alert %s", alert_id)


async def fire_webhook(alerts: list[DriftAlert]) -> None:
    """Send drift alerts to configured webhook URL (Slack, PagerDuty, etc)."""
    url = settings.DRIFT_WEBHOOK_URL
    if not url:
        return

    payload = {
        "text": f"🚨 Monolith Breaker Drift Alert: {len(alerts)} violation(s) detected",
        "alerts": [
            {
                "id": a.id,
                "service": a.service_name,
                "type": a.violation_type.value,
                "detected_at": a.detected_at.isoformat(),
            }
            for a in alerts
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        logger.info("Fired webhook to %s — %d alerts", url, len(alerts))
    except Exception as exc:
        logger.error("Webhook failed (%s): %s", url, exc)
