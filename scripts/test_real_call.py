"""Quick end-to-end test: bootstrap -> loop -> assemble -> print."""

import asyncio
import os
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["PYTHONIOENCODING"] = "utf-8"

# Suppress HF unauthenticated warning BEFORE any imports that trigger it
import logging
logging.getLogger("huggingface_hub.utils._http").setLevel(logging.ERROR)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from backend.app.blueprint.default import DEFAULT_BLUEPRINT
from backend.app.generation.loop import run_generation_loop
from backend.app.generation.assembler import assemble_test, save_test
from backend.app.storage.jobs import create_job
from backend.app.schemas.job import GenerationJob, JobStatus
from backend.app.storage.db import init_db
from backend.app.logging_config import configure_logging

configure_logging(log_level="ERROR")


async def main():
    bp = DEFAULT_BLUEPRINT
    print(f"Blueprint: {bp.name} ({bp.total_questions} questions, {len(bp.modules)} modules)")

    await init_db()
    total_slots = sum(len(m.slots) for m in bp.modules)
    job_id = f"test-{int(time.time())}"
    job = GenerationJob(
        id=job_id, blueprint_id=bp.id,
        status=JobStatus.PENDING, total_slots=total_slots,
        completed_slots=0, failed_slots=0,
    )
    try:
        await create_job(job)
    except Exception:
        pass

    print(f"Running generation loop ({total_slots} slots)...")
    results = await run_generation_loop(bp, job_id)
    print(f"Generated {len(results)} question records")

    if not results:
        print("No questions generated.")
        return

    test = assemble_test(results, bp, job_id)
    print(f"\nAssembled test: {test.id} - {test.total_questions} questions, {len(test.modules)} modules")

    for mod in test.modules:
        print(f"\n  Module {mod.module_number} ({mod.module_type.value}): {mod.question_count} Qs")
        for q in mod.questions[:2]:
            print(f"    Q{q.question_number}: {q.question_text[:80]}")
        if mod.question_count > 2:
            print(f"    ... and {mod.question_count - 2} more")

    q = test.questions[0]
    print(f"\n--- Sample ---")
    print(f"Q{q.question_number}: {q.question_text}")
    for c in q.choices:
        print(f"  {c.letter}. {c.text}")
    print(f"Correct: {q.correct_answer}")
    print(f"Skill: {q.skill_type.value}  |  Difficulty: {q.difficulty.value}")

    await save_test(test)
    print(f"\nSaved test to inventory. All good!")


if __name__ == "__main__":
    asyncio.run(main())
