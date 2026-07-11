"""
EST Synthesizer — Generation Progress SSE Endpoint (T17)

GET /api/tests/{job_id}/progress
    Server-Sent Events stream that pushes job status updates to the client
    in real time.  The frontend can use EventSource (or a fetch polyfill)
    to consume this stream and update a progress bar.

Events:
    event: progress
    data: {"job_id": "...", "status": "generating", "progress": 42}

    event: complete
    data: {"job_id": "...", "status": "completed", "progress": 100,
           "result_test_id": "abc123", "student_pdf_path": "...",
           "teacher_pdf_path": "..."}

    event: error
    data: {"job_id": "...", "status": "failed", "progress": 0,
           "error_message": "..."}

Design:
    - FastAPI router at prefix /api/tests (same as generate router)
    - Uses StreamingResponse with asyncio.sleep polling (1 Hz)
    - Polls the job from SQLite via get_job()
    - Stream ends when the job reaches a terminal state (COMPLETED / FAILED)
"""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.schemas import JobStatus
from backend.app.storage.jobs import get_job

router = APIRouter(prefix="/api/tests", tags=["generation"])
log = structlog.get_logger(__name__)

POLL_INTERVAL = 1.0  # seconds between job-status checks


async def _event_stream(job_id: str):
    """Yield SSE events.  Polls the job record until a terminal state."""
    terminal_states = {JobStatus.COMPLETED, JobStatus.FAILED}
    last_status: str | None = None

    while True:
        job = await get_job(job_id)
        if job is None:
            yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        status = job.status.value
        progress = job.progress

        if status != last_status:
            payload = {
                "job_id": job.id,
                "status": status,
                "progress": progress,
                "result_test_id": job.result_test_id,
                "error_message": job.error_message,
            }
            if job.status == JobStatus.COMPLETED:
                yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
                return
            elif job.status == JobStatus.FAILED:
                yield f"event: error\ndata: {json.dumps(payload)}\n\n"
                return
            else:
                yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
            last_status = status

        await asyncio.sleep(POLL_INTERVAL)


@router.get("/{job_id}/progress")
async def get_progress(job_id: str):
    """SSE endpoint: push job progress updates to the client in real time.

    The client opens this endpoint with an EventSource (or fetch + ReadableStream)
    and receives events as the job progresses through the generation pipeline.
    """
    # Verify the job exists before starting the stream
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return StreamingResponse(
        _event_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
