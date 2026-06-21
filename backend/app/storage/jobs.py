"""EST Synthesizer - Generation Job CRUD."""

from __future__ import annotations

import structlog
from datetime import datetime, timezone

from backend.app.schemas import GenerationJob, JobStatus
from backend.app.storage.db import _ensure_utc, get_connection

logger = structlog.get_logger(__name__)

INSERT_JOB_SQL = """
INSERT INTO generation_jobs
    (id, status, blueprint_id, total_slots, completed_slots,
     failed_slots, result_test_id, error_message, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
SELECT_JOB_SQL = "SELECT * FROM generation_jobs WHERE id = ?"
UPDATE_JOB_SQL = """
UPDATE generation_jobs
SET    status          = ?,
       completed_slots = completed_slots + COALESCE(?, 0),
       failed_slots    = failed_slots    + COALESCE(?, 0),
       result_test_id  = COALESCE(?, result_test_id),
       error_message   = COALESCE(?, error_message),
       updated_at      = ?
WHERE  id = ?
"""


async def create_job(job: GenerationJob) -> None:
    try:
        async with get_connection() as db:
            await db.execute(INSERT_JOB_SQL, (
                job.id, job.status.value, job.blueprint_id,
                job.total_slots, job.completed_slots, job.failed_slots,
                job.result_test_id, job.error_message,
                _ensure_utc(job.created_at).isoformat(),
                _ensure_utc(job.updated_at).isoformat(),
            ))
            await db.commit()
        logger.debug("Job created", job_id=job.id)
    except Exception:
        logger.exception("Failed to create job", job_id=job.id)
        raise


async def get_job(job_id: str) -> GenerationJob | None:
    try:
        async with get_connection() as db:
            async with db.execute(SELECT_JOB_SQL, (job_id,)) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        return GenerationJob(
            id=row["id"], status=JobStatus(row["status"]),
            blueprint_id=row["blueprint_id"],
            total_slots=row["total_slots"],
            completed_slots=row["completed_slots"],
            failed_slots=row["failed_slots"],
            result_test_id=row["result_test_id"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
    except Exception:
        logger.exception("Failed to fetch job", job_id=job_id)
        raise


async def update_job_status(
    job_id: str, status: JobStatus,
    completed_slots: int | None = None,
    failed_slots: int | None = None,
    error_message: str | None = None,
) -> None:
    try:
        now = datetime.now(timezone.utc).isoformat()
        async with get_connection() as db:
            await db.execute(UPDATE_JOB_SQL, (
                status.value, completed_slots, failed_slots,
                error_message, error_message, now, job_id,
            ))
            await db.commit()
        logger.debug("Job updated", job_id=job_id, status=status.value)
    except Exception:
        logger.exception("Failed to update job", job_id=job_id)
        raise
