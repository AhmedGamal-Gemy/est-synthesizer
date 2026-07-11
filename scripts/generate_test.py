"""
EST Synthesizer — Generate Test CLI (T15)

One command that drives the full pipeline:

    uv run python scripts/generate_test.py [--blueprint default_blueprint_v1] [--no-pdf] [--log-level ERROR]

Steps:
  1. Resolve blueprint (CLI arg → DB lookup → fall back to DEFAULT_BLUEPRINT in code)
  2. Init SQLite
  3. Run the generation loop (T11) — passage retrieval + LLM + retries
  4. Assemble the test (T12) — questions into a GeneratedTest
  5. Fetch passage text from Qdrant so the PDF can show the actual passage
  6. Render student + teacher PDFs (T14) unless --no-pdf
  7. Save the test to inventory with PDF paths

Prereqs: Qdrant running (`docker compose up -d`), passages bootstrapped
(`scripts/bootstrap_library.py`), and an LLM reachable (either direct Mistral
key or via the LiteLLM proxy).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Suppress HF unauthenticated warning BEFORE any imports that trigger it
import logging
logging.getLogger("huggingface_hub.utils._http").setLevel(logging.ERROR)
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from backend.app.blueprint.default import DEFAULT_BLUEPRINT  # noqa: E402
from backend.app.generation.assembler import assemble_test, save_test  # noqa: E402
from backend.app.generation.loop import run_generation_loop  # noqa: E402
from backend.app.logging_config import configure_logging  # noqa: E402
from backend.app.pdf.renderer import render_student_pdf, render_teacher_pdf  # noqa: E402
from backend.app.schemas import TestBlueprint  # noqa: E402
from backend.app.schemas.job import GenerationJob, JobStatus  # noqa: E402
from backend.app.storage.blueprints import get_blueprint  # noqa: E402
from backend.app.storage.db import init_db  # noqa: E402
from backend.app.storage.jobs import create_job  # noqa: E402
from backend.app.storage.qdrant import QdrantManager, COLLECTION_LONG, COLLECTION_SHORT  # noqa: E402


async def _resolve_blueprint(bp_id: str) -> TestBlueprint:
    """Load blueprint by id from DB; fall back to the DEFAULT constant if missing."""
    if not bp_id:
        return DEFAULT_BLUEPRINT

    row = await get_blueprint(bp_id)
    if row is None:
        print(f"Blueprint {bp_id!r} not found in DB. Using DEFAULT_BLUEPRINT.")
        return DEFAULT_BLUEPRINT

    try:
        return TestBlueprint.model_validate(row["blueprint_json"], strict=False)
    except Exception as exc:
        print(
            f"Blueprint {bp_id!r} in DB failed validation ({exc}). "
            "Using DEFAULT_BLUEPRINT."
        )
        return DEFAULT_BLUEPRINT


async def _fetch_passage_texts(passage_ids: set[str]) -> dict[str, str]:
    """Pull passage text for each unique id so the PDF can show the actual passage."""
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
                    collection_name=COLLECTION_SHORT, ids=[pid],
                    with_payload=True, with_vectors=False,
                )
            if hits:
                out[pid] = hits[0].payload.get("text", "")
    finally:
        await qm.close()
    return out


async def _run(bp_id: str, render_pdfs: bool, log_level: str) -> int:
    configure_logging(log_level=log_level)

    bp = await _resolve_blueprint(bp_id)
    total_slots = sum(len(m.slots) for m in bp.modules)
    print(f"Blueprint: {bp.name} ({bp.total_questions} questions, {len(bp.modules)} modules, {total_slots} slots)")

    await init_db()
    job_id = f"cli-{int(time.time())}"
    job = GenerationJob(
        id=job_id, blueprint_id=bp.id,
        status=JobStatus.PENDING, total_slots=total_slots,
        completed_slots=0, failed_slots=0,
    )
    try:
        await create_job(job)
    except Exception:
        pass  # best-effort job tracking

    print(f"Running generation loop ({total_slots} slots at {os.environ.get('MISTRAL_RATE_LIMIT', '1')} req/s)...")
    results = await run_generation_loop(bp, job_id)
    print(f"Generated {len(results)} question records")

    if not results:
        print("No questions generated — nothing to assemble.")
        return 1

    test = assemble_test(results, bp, job_id)
    print(f"Assembled test: {test.id} - {test.total_questions} questions, {len(test.modules)} modules")

    if render_pdfs:
        passage_ids = {r["passage_id"] for r in results}
        try:
            passage_text = await _fetch_passage_texts(passage_ids)
        except Exception as exc:
            print(f"Warning: could not fetch passage text ({exc}); PDFs will show placeholders.")
            passage_text = {}
        student = render_student_pdf(test, passage_text=passage_text)
        teacher = render_teacher_pdf(test, passage_text=passage_text)
        test.student_pdf_path = student
        test.teacher_pdf_path = teacher
        print(f"Student PDF: {student}")
        print(f"Teacher PDF: {teacher}")

    await save_test(test)
    print(f"Saved test {test.id} to inventory.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one EST test end-to-end.")
    parser.add_argument(
        "--blueprint", default="default_blueprint_v1",
        help="Blueprint id (default: default_blueprint_v1). Empty string '' forces DEFAULT_BLUEPRINT.",
    )
    parser.add_argument(
        "--no-pdf", action="store_true",
        help="Skip PDF rendering — just save the test record to inventory.",
    )
    parser.add_argument(
        "--log-level", default=os.environ.get("LOG_LEVEL", "ERROR"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: ERROR or $LOG_LEVEL).",
    )
    args = parser.parse_args()
    bp_id = args.blueprint if args.blueprint else ""
    return asyncio.run(_run(bp_id, not args.no_pdf, args.log_level))


if __name__ == "__main__":
    raise SystemExit(main())
