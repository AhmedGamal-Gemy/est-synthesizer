"""Assemble generation loop output into a structured GeneratedTest."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import List

import structlog

from backend.app.schemas import (
    Difficulty, GeneratedModule, GeneratedPassageBlock, GeneratedQuestion,
    GeneratedTest, LLMQuestionOutput, ModuleType, TestBlueprint,
)
from backend.app.storage.tests import save_inventory_record

log = structlog.get_logger(__name__)


def assemble_test(questions: List[dict], blueprint: TestBlueprint, job_id: str) -> GeneratedTest:
    """Convert flat question records into a GeneratedTest grouped by module/passage."""
    test_id = uuid.uuid4().hex[:12]
    all_qs: List[GeneratedQuestion] = []

    for i, rec in enumerate(questions, 1):
        q: LLMQuestionOutput = rec["question"]
        all_qs.append(GeneratedQuestion(
            id=uuid.uuid4().hex[:12], 
            passage_id=rec["passage_id"],
            module_number=rec["module_number"], 
            slot_number=rec["slot_number"],
            question_number=i, 
            question_text=q.question_text, 
            choices=list(q.choices),
            correct_answer=q.correct_answer, 
            explanation=q.explanation,
            supporting_line=q.supporting_line, 
            skill_type=q.skill_type, 
            difficulty=q.difficulty,
        ))

    # Group by (module_number, passage_id)
    groups: dict[tuple[int, str], list[GeneratedQuestion]] = {}
    for gq in all_qs:
        groups.setdefault((gq.module_number, gq.passage_id), []).append(gq)

    mod_pbs: dict[tuple[int, str], GeneratedPassageBlock] = {
        k: GeneratedPassageBlock(passage_id=k[1], passage_text="", questions=qs)
        for k, qs in groups.items()
    }

    modules = []
    for mod_num in sorted({q.module_number for q in all_qs}):
        mod_type = next((r["module_type"] for r in questions if r["module_number"] == mod_num), ModuleType.WRITING)
        mod_qs = [q for q in all_qs if q.module_number == mod_num]
        modules.append(GeneratedModule(
            module_number=mod_num, module_type=mod_type,
            passages=[pb for (mn, _), pb in mod_pbs.items() if mn == mod_num],
            questions=mod_qs, question_count=len(mod_qs),
        ))

    _warn_on_distribution_mismatch(all_qs, blueprint)

    return GeneratedTest(
        id=test_id, job_id=job_id, blueprint_id=blueprint.id,
        questions=all_qs, modules=modules, total_questions=len(all_qs),
    )


def _warn_on_distribution_mismatch(questions: List[GeneratedQuestion], blueprint: TestBlueprint) -> None:
    """Log warnings if skill types or difficulty distributions deviate from the blueprint."""
    skill_counts = Counter(q.skill_type for q in questions)
    for mod in blueprint.modules:
        for slot in mod.slots:
            if slot.skill_type not in skill_counts:
                log.warning("Missing skill type", skill=slot.skill_type.value, slot=slot.slot_number, module=mod.module_number)

    total = len(questions)
    if total:
        diff_counts = Counter(q.difficulty for q in questions)
        for diff in Difficulty:
            actual = diff_counts.get(diff, 0) / total
            expected = blueprint.difficulty_distribution.get(diff.value, 0.0)
            if abs(actual - expected) > 0.1:
                log.warning("Difficulty mismatch", diff=diff.value, actual=round(actual, 3), expected=expected)


async def save_test(test: GeneratedTest) -> None:
    """Persist a generated test to storage."""
    await save_inventory_record(test)
