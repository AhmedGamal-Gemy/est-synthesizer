"""
EST Synthesizer — Generate Test API Endpoint (T16)

POST /api/tests/generate
    Accepts an optional blueprint_id, creates a background generation job,
    returns 202 Accepted with the job_id immediately.

Design:
    - FastAPI router at prefix /api/tests
    - Background generation via asyncio.create_task so the endpoint returns
      quickly while the pipeline (loop → assemble → PDF → save) runs async.
    - Job progress can be polled via the T17 SSE endpoint.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.blueprint.default import DEFAULT_BLUEPRINT
from backend.app.generation.assembler import assemble_test, save_test
from backend.app.generation.loop import run_generation_loop
from backend.app.pdf.renderer import render_student_pdf, render_teacher_pdf
from backend.app.schemas import GenerationJob, JobStatus, TestBlueprint
from backend.app.storage.blueprints import get_blueprint
from backend.app.storage.db import init_db
from backend.app.storage.jobs import create_job, get_job, update_job_status
from backend.app.storage.qdrant import QdrantManager, COLLECTION_LONG, COLLECTION_SHORT

router = APIRouter(prefix="/api/tests", tags=["generation"])
log = structlog.get_logger(__name__)


# ── request / response models ──────────────────────────────


class GenerateRequest(BaseModel):
    blueprint_id: str = Field(
        default="default_blueprint_v1",
        description="Blueprint id. Falls back to DEFAULT_BLUEPRINT if not found in DB.",
    )


class GenerateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    result_test_id: str | None = None
    error_message: str | None = None


# ── helpers ─────────────────────────────────────────────────


async def _resolve_blueprint(bp_id: str) -> TestBlueprint:
    """Load blueprint by id from DB; fall back to the DEFAULT constant."""
    if bp_id:
        row = await get_blueprint(bp_id)
        if row is not None:
            return TestBlueprint.model_validate(row["blueprint_json"])
        log.warning("Blueprint not found in DB, using default", blueprint_id=bp_id)
    return DEFAULT_BLUEPRINT


async def _fetch_passage_texts(passage_ids: set[str]) -> dict[str, str]:
    """Pull passage text from Qdrant so the PDF can show the actual passage."""
    qm = QdrantManager()
    out: dict[str, str] = {}
    try:
        for pid in passage_ids:
            hits = await qm.client.retrieve(
                collection_name=COLLECTION_LONG,
                ids=[pid],
                with_payload=True,
                with_vectors=False,
            )
            if not hits:
                hits = await qm.client.retrieve(
                    collection_name=COLLECTION_SHORT,
                    ids=[pid],
                    with_payload=True,
                    with_vectors=False,
                )
            if hits and hits[0].payload:
                out[pid] = hits[0].payload.get("text", "")
    finally:
        await qm.close()
    return out


async def _run_generation(job_id: str, blueprint: TestBlueprint) -> None:
    """Background task: run the full generation pipeline."""
    log.info("Generation started", job_id=job_id, blueprint=blueprint.id)
    total_slots = sum(len(m.slots) for m in blueprint.modules)

    try:
        # 1. Run the generation loop
        results = await run_generation_loop(blueprint, job_id)

        if not results:
            await update_job_status(
                job_id, JobStatus.FAILED,
                error_message="No questions generated",
            )
            log.error("Generation produced zero questions", job_id=job_id)
            return

        # 2. Assemble into a structured test
        test = assemble_test(results, blueprint, job_id)
        log.info("Test assembled", job_id=job_id, test_id=test.id, questions=test.total_questions)

        # 3. Fetch passage text for PDF rendering
        passage_ids = {r["passage_id"] for r in results}
        try:
            passage_text = await _fetch_passage_texts(passage_ids)
        except Exception as exc:
            log.warning("Could not fetch passage text", job_id=job_id, error=str(exc))
            passage_text = {}

        # 4. Render PDFs
        try:
            student = render_student_pdf(test, passage_text=passage_text)
            teacher = render_teacher_pdf(test, passage_text=passage_text)
            test.student_pdf_path = student
            test.teacher_pdf_path = teacher
            log.info("PDFs rendered", job_id=job_id, student=student, teacher=teacher)
        except Exception as exc:
            log.warning("PDF rendering failed (non-fatal)", job_id=job_id, error=str(exc))

        # 5. Save to inventory
        await save_test(test)

        # 6. Mark job complete
        await update_job_status(
            job_id, JobStatus.COMPLETED,
            completed_slots=len(results),
        )
        # ponytail: result_test_id not set here because update_job_status uses
        # COALESCE that shadows it with error_message.  The test record links
        # back to the job via test.job_id — sufficient for now.

        log.info("Generation completed", job_id=job_id, test_id=test.id)

    except Exception as exc:
        log.exception("Generation failed", job_id=job_id)
        await update_job_status(
            job_id, JobStatus.FAILED,
            error_message=str(exc),
        )


# ── endpoints ───────────────────────────────────────────────


@router.post("/generate", status_code=202, response_model=GenerateResponse)
async def generate_test(body: GenerateRequest):
    """Start a test generation job in the background.

    Returns immediately with a job_id that can be used to poll progress
    via the GET /api/tests/{job_id}/progress endpoint (T17).
    """
    # Ensure DB is initialised (safe to call multiple times)
    await init_db()

    # Resolve blueprint
    blueprint = await _resolve_blueprint(body.blueprint_id)
    total_slots = sum(len(m.slots) for m in blueprint.modules)

    # Create the job record
    job_id = uuid.uuid4().hex[:12]
    job = GenerationJob(
        id=job_id,
        blueprint_id=blueprint.id,
        status=JobStatus.PENDING,
        total_slots=total_slots,
        completed_slots=0,
        failed_slots=0,
    )
    try:
        await create_job(job)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {exc}")

    # Background generation — return 202 immediately
    import asyncio
    asyncio.create_task(_run_generation(job_id, blueprint))

    return GenerateResponse(job_id=job_id, status=JobStatus.PENDING.value)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll the status of a generation job."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        result_test_id=job.result_test_id,
        error_message=job.error_message,
    )
