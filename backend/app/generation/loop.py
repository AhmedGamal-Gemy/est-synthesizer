"""Generation loop: retrieve passages in parallel, generate slots sequentially."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import List

import structlog
from pydantic import ValidationError

from backend.app.generation.caller import get_queue
from backend.app.generation.exceptions import LLMCallError
from backend.app.generation.prompts import build_system_prompt, build_user_prompt
from backend.app.generation.validator import validate_question
from backend.app.schemas import (
    JobStatus, ModuleType, Passage, PassageCategory, PassageType,
    LLMBatchOutput, LLMQuestionOutput, TestBlueprint, ModuleSlot,
)
from backend.app.storage.jobs import update_job_status
from backend.app.storage.qdrant import QdrantManager

log = structlog.get_logger(__name__)
MAX_RETRIES = 3
FAILURE_THRESHOLD = 0.20


class GenerationFailedError(Exception):
    """More than 20% of slots failed."""


@dataclass
class _SlotResult:
    passage_id: str
    module_number: int
    module_type: ModuleType
    slot_number: int
    slot_config: ModuleSlot
    questions: List[LLMQuestionOutput] = field(default_factory=list)


async def _retrieve_passages(qdrant, blueprint) -> dict[tuple[int, int], Passage]:
    """One distinct passage per unique (module, slot_number), fetched in parallel per module type."""
    groups: dict[ModuleType, list[tuple[int, int]]] = {}
    for mod in blueprint.modules:
        seen = set()
        for slot in mod.slots:
            key = (mod.module_number, slot.slot_number)
            if key not in seen:
                seen.add(key)
                groups.setdefault(mod.module_type, []).append(key)

    async def _fetch_group(module_type, keys):
        if module_type == ModuleType.WRITING:
            col, q, fil = "long_passages", "essay argumentative text", {"passage_type": "long"}
        elif module_type == ModuleType.READING_LONG:
            col, q, fil = "long_passages", "narrative scientific historical text", {"passage_type": "long"}
        else:
            col, q, fil = "short_passages", "informational narrative text", {"passage_type": "short"}
        results = await qdrant.search_passages(query_text=q, collection=col, filters=fil, limit=len(keys))
        out = {}
        n = len(results)
        if n == 0:
            return out
        if n < len(keys):
            log.warning(
                "Not enough distinct passages for module type, recycling",
                module_type=module_type.value, needed=len(keys), available=n,
            )
        for i, key in enumerate(keys):
            r = results[i % n]
            p = r["payload"] or {}
            out[key] = Passage(
                id=r["id"], text=p.get("text", ""),
                source_url=p.get("source_url", ""), source_title=p.get("source_title", ""),
                passage_type=PassageType(p.get("passage_type", "long")),
                passage_category=PassageCategory(p.get("passage_category", "essay")),
                word_count=p.get("word_count", 0), reading_level=p.get("reading_level", 0.0),
            )
        return out

    gathered = await asyncio.gather(*[_fetch_group(mt, keys) for mt, keys in groups.items()])
    merged: dict[tuple[int, int], Passage] = {}
    for d in gathered:
        merged.update(d)
    return merged


async def _generate_slot(slot, module_number, module_type, passage) -> _SlotResult:
    """One slot with retries. Empty questions list = exhausted retries."""
    result = _SlotResult(passage_id=passage.id, module_number=module_number,
                         module_type=module_type, slot_number=slot.slot_number, slot_config=slot)
    sp, up = build_system_prompt(), build_user_prompt(passage, None, slot, module_type)
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = await get_queue().submit(system_prompt=sp, user_prompt=up, schema=LLMBatchOutput)
            batch = LLMBatchOutput(**raw)
            valid = [q for q in batch.questions if validate_question(q, passage.text)[0]]
            if valid:
                result.questions = valid
                return result
            last_err = "All questions failed validation"
        except (ValidationError, LLMCallError) as exc:
            last_err = str(exc)
            log.warning("LLM failed, retrying", attempt=attempt, error=last_err,
                        module=module_number, slot=slot.slot_number)
    log.error("Slot failed after retries", module=module_number, slot=slot.slot_number, error=last_err)
    return result


async def run_generation_loop(blueprint: TestBlueprint, job_id: str) -> list[dict]:
    """Parallel passage retrieval, then sequential slot generation. Returns question-level records."""
    qdrant = QdrantManager()
    total_slots = sum(len(m.slots) for m in blueprint.modules)
    await update_job_status(job_id, JobStatus.GENERATING, completed_slots=0)

    passages = await _retrieve_passages(qdrant, blueprint)
    completed = failed = 0
    all_results: list[_SlotResult] = []

    for mod in blueprint.modules:
        for slot in mod.slots:
            passage = passages.get((mod.module_number, slot.slot_number))
            if passage is None:
                failed += 1
                continue
            sr = await _generate_slot(slot, mod.module_number, mod.module_type, passage)
            all_results.append(sr)
            if sr.questions:
                completed += 1
            else:
                failed += 1
            await update_job_status(job_id, JobStatus.GENERATING, completed_slots=completed, failed_slots=failed)

    await qdrant.close()

    failure_rate = failed / total_slots if total_slots else 0
    if failure_rate > FAILURE_THRESHOLD:
        await update_job_status(job_id, JobStatus.FAILED,
                                error_message=f"Failure rate {failure_rate:.0%} exceeds threshold {FAILURE_THRESHOLD:.0%}")
        raise GenerationFailedError(f"{failed}/{total_slots} slots failed ({failure_rate:.0%})")

    return [
        {"question": q, "passage_id": sr.passage_id, "module_number": sr.module_number,
         "module_type": sr.module_type, "slot_number": sr.slot_number}
        for sr in all_results for q in sr.questions
    ]
