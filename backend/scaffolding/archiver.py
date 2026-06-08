# backend/scaffolding/archiver.py
"""
Archiver — Zips all outputs keyed by job_id.

Packages all generated files into a downloadable zip archive.
Used by orchestrator and routes/output.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)


def create_archive(job_id: str) -> str:
    """
    Create a zip archive of all generated outputs for a job.

    Zips the entire services/ and contracts/ directories under
    OUTPUT_DIR/{job_id}/ into a single downloadable archive.

    Returns the absolute path to the created zip file.
    """
    output_dir = Path(settings.OUTPUT_DIR) / job_id
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    zip_filename = f"monolith-breaker-{job_id}.zip"
    zip_path = output_dir / zip_filename

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Walk all files in the output directory
        for file_path in sorted(output_dir.rglob("*")):
            if file_path.is_file() and file_path != zip_path:
                # Store with relative path from the output directory
                arcname = file_path.relative_to(output_dir)
                zinfo = zipfile.ZipInfo.from_file(file_path, arcname)
                # Ensure files are world-readable (0644) when extracted on host
                zinfo.external_attr = 0o100644 << 16
                zf.writestr(zinfo, file_path.read_bytes())

    file_size_mb = zip_path.stat().st_size / (1024 * 1024)
    logger.info("Created archive: %s (%.2f MB)", zip_path, file_size_mb)
    return str(zip_path)
