# scripts/drift_cron.py
"""
Drift Cron — Standalone drift scan runner for K8s CronJob.

Usage:
    python scripts/drift_cron.py                    # scan all registered services
    python scripts/drift_cron.py --job-id <uuid>   # scan specific job
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db import neo4j_client
from backend.drift.alerter import fire_webhook, write_alerts
from backend.drift.detector import detect_violations
from backend.drift.scanner import scan_service_repo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_cron(job_id: str | None = None) -> int:
    """
    Run drift scans. Returns exit code (0 = success, 1 = error).
    """
    await neo4j_client.get_driver()

    total_alerts = 0

    if job_id:
        job_ids = [job_id]
    else:
        # Query all jobs with registered service repos
        records = await neo4j_client.run_query(
            "MATCH (b:BoundedContext) RETURN DISTINCT b.job_id AS job_id"
        )
        job_ids = [r["job_id"] for r in records if r.get("job_id")]

    if not job_ids:
        logger.info("No jobs found for drift scanning")
        await neo4j_client.close()
        return 0

    for jid in job_ids:
        logger.info("--- Scanning job %s ---", jid)

        # Get service repos from Neo4j
        services = await neo4j_client.run_query(
            """
            MATCH (b:BoundedContext {job_id: $job_id})
            WHERE b.repo_path IS NOT NULL
            RETURN b.name AS name, b.repo_path AS repo_path
            """,
            {"job_id": jid},
        )

        if not services:
            logger.info("No registered service repos for job %s", jid)
            continue

        for svc in services:
            name = svc["name"]
            repo_path = svc["repo_path"]
            logger.info("Scanning %s at %s", name, repo_path)

            current_graph = scan_service_repo(repo_path)
            violations = await detect_violations(current_graph, jid)

            if violations:
                await write_alerts(violations)
                await fire_webhook(violations)
                total_alerts += len(violations)
                logger.warning("  %s: %d violations", name, len(violations))
            else:
                logger.info("  %s: clean ✓", name)

    logger.info("=== Drift cron complete: %d total alerts ===", total_alerts)
    await neo4j_client.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run scheduled drift detection scans")
    parser.add_argument("--job-id", default=None, help="Scan specific job (default: all)")
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(run_cron(args.job_id))
        sys.exit(exit_code)
    except Exception as exc:
        logger.exception("Drift cron failed: %s", exc)
        sys.exit(1)
