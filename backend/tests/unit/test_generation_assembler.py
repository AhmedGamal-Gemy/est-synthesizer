"""Unit tests for backend.app.generation.assembler — test assembly + save."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.generation.assembler import assemble_test, save_test
from backend.app.schemas import (
    Difficulty,
    DistractorRole,
    ModuleConfig,
    ModuleSlot,
    ModuleType,
    SkillType,
    TestBlueprint,
)
from backend.app.schemas.question import AnswerChoice, LLMQuestionOutput


# ── Helpers ──────────────────────────────────────────────────

_E = Difficulty.EASY
_M = Difficulty.MEDIUM
_H = Difficulty.HARD


def _make_blueprint() -> TestBlueprint:
    """Minimal blueprint with 2 modules, 4 slots total."""
    return TestBlueprint(
        id="bp-test-1",
        name="Test Blueprint",
        modules=[
            ModuleConfig(
                module_number=1,
                module_type=ModuleType.WRITING,
                slots=[
                    ModuleSlot(
                        slot_number=1,
                        skill_type=SkillType.SENTENCE_FORMATION,
                        difficulty=_E,
                        question_count=2,
                        easy_count=2,
                        medium_count=0,
                        hard_count=0,
                    ),
                    ModuleSlot(
                        slot_number=2,
                        skill_type=SkillType.PUNCTUATION,
                        difficulty=_M,
                        question_count=1,
                        easy_count=0,
                        medium_count=1,
                        hard_count=0,
                    ),
                ],
                has_figure=False,
                wordy_answer_style=True,
            ),
            ModuleConfig(
                module_number=2,
                module_type=ModuleType.READING_SHORT,
                slots=[
                    ModuleSlot(
                        slot_number=1,
                        skill_type=SkillType.VOCABULARY_IN_CONTEXT,
                        difficulty=_E,
                        question_count=1,
                        easy_count=1,
                        medium_count=0,
                        hard_count=0,
                    ),
                    ModuleSlot(
                        slot_number=2,
                        skill_type=SkillType.INFORMATION_AND_IDEAS,
                        difficulty=_H,
                        question_count=1,
                        easy_count=0,
                        medium_count=0,
                        hard_count=1,
                    ),
                ],
                has_figure=False,
                wordy_answer_style=False,
            ),
        ],
        total_questions=5,
        difficulty_distribution={"easy": 0.4, "medium": 0.2, "hard": 0.4},
    )


def _make_question_record(
    module_number: int,
    slot_number: int,
    skill_type: SkillType = SkillType.SENTENCE_FORMATION,
    difficulty: Difficulty = Difficulty.EASY,
    passage_id: str = "passage-1",
) -> dict:
    """Return a question record dict as produced by the generation loop."""
    return {
        "question": LLMQuestionOutput(
            question_text="What is the main idea of the passage?",
            choices=[
                AnswerChoice(
                    letter="A",
                    text="The correct choice.",
                    distractor_role=DistractorRole.BEST_ANSWER,
                ),
                AnswerChoice(
                    letter="B",
                    text="A plausible but wrong choice.",
                    distractor_role=DistractorRole.GOOD_NOT_BEST,
                ),
                AnswerChoice(
                    letter="C",
                    text="An incorrect choice.",
                    distractor_role=DistractorRole.COMPLETELY_WRONG,
                ),
                AnswerChoice(
                    letter="D",
                    text="Another incorrect choice.",
                    distractor_role=DistractorRole.COMPLETELY_WRONG,
                ),
            ],
            correct_answer="A",
            explanation="Because A is correct.",
            supporting_line="Passage supports A.",
            skill_type=skill_type,
            difficulty=difficulty,
        ),
        "passage_id": passage_id,
        "module_number": module_number,
        "module_type": ModuleType.WRITING if module_number == 1 else ModuleType.READING_SHORT,
        "slot_number": slot_number,
    }


# ── Tests ────────────────────────────────────────────────────


class TestAssembleTest:
    """Tests for ``assemble_test``."""

    def test_assembles_single_module(self):
        """Two questions in module 1 → one module, two questions."""
        questions = [
            _make_question_record(
                module_number=1, slot_number=1,
                passage_id="p1",
            ),
            _make_question_record(
                module_number=1, slot_number=2,
                passage_id="p1", skill_type=SkillType.PUNCTUATION,
                difficulty=Difficulty.MEDIUM,
            ),
        ]
        blueprint = _make_blueprint()
        result = assemble_test(questions, blueprint, job_id="job-001")

        assert len(result.modules) == 1
        assert result.modules[0].module_number == 1
        assert result.modules[0].module_type == ModuleType.WRITING
        assert result.modules[0].question_count == 2
        assert len(result.modules[0].questions) == 2

    def test_sequential_question_numbers(self):
        """Questions are numbered 1, 2, 3 … across the entire test."""
        questions = [
            _make_question_record(module_number=1, slot_number=1, passage_id="p1"),
            _make_question_record(module_number=1, slot_number=2, passage_id="p1"),
            _make_question_record(module_number=2, slot_number=1, passage_id="p2"),
        ]
        blueprint = _make_blueprint()
        result = assemble_test(questions, blueprint, job_id="job-002")

        numbers = [q.question_number for q in result.questions]
        assert numbers == [1, 2, 3]

    def test_groups_questions_by_passage_within_module(self):
        """Questions on the same passage+module go into one passage block."""
        questions = [
            _make_question_record(
                module_number=1, slot_number=1, passage_id="p1",
            ),
            _make_question_record(
                module_number=1, slot_number=2, passage_id="p1",
            ),
            _make_question_record(
                module_number=1, slot_number=3, passage_id="p2",
                skill_type=SkillType.PUNCTUATION, difficulty=Difficulty.MEDIUM,
            ),
        ]
        blueprint = _make_blueprint()
        result = assemble_test(questions, blueprint, job_id="job-003")

        mod1 = result.modules[0]
        assert len(mod1.passages) == 2

        # passage-1 block has 2 questions
        p1_block = next(pb for pb in mod1.passages if pb.passage_id == "p1")
        assert len(p1_block.questions) == 2

        # passage-2 block has 1 question
        p2_block = next(pb for pb in mod1.passages if pb.passage_id == "p2")
        assert len(p2_block.questions) == 1

    def test_correct_total_questions(self):
        """total_questions matches the length of the input list."""
        questions = [
            _make_question_record(module_number=1, slot_number=1, passage_id="p1"),
            _make_question_record(module_number=1, slot_number=2, passage_id="p1"),
            _make_question_record(module_number=2, slot_number=1, passage_id="p2"),
            _make_question_record(
                module_number=2, slot_number=2, passage_id="p2",
                skill_type=SkillType.INFORMATION_AND_IDEAS, difficulty=Difficulty.HARD,
            ),
        ]
        blueprint = _make_blueprint()
        result = assemble_test(questions, blueprint, job_id="job-004")
        assert result.total_questions == 4

    def test_blueprint_and_job_id_passed_through(self):
        """Blueprint ID and job ID are correctly set on the result."""
        questions = [
            _make_question_record(module_number=1, slot_number=1, passage_id="p1"),
        ]
        blueprint = _make_blueprint()
        result = assemble_test(questions, blueprint, job_id="job-005")
        assert result.blueprint_id == "bp-test-1"
        assert result.job_id == "job-005"

    def test_empty_questions_list(self):
        """Empty input → test with zero questions and modules."""
        blueprint = _make_blueprint()
        result = assemble_test([], blueprint, job_id="job-006")
        assert result.total_questions == 0
        assert result.questions == []
        assert result.modules == []

    def test_multiple_modules(self):
        """Questions spanning 2 modules produce 2 GeneratedModules."""
        questions = [
            _make_question_record(module_number=1, slot_number=1, passage_id="p1"),
            _make_question_record(module_number=2, slot_number=1, passage_id="p2"),
        ]
        blueprint = _make_blueprint()
        result = assemble_test(questions, blueprint, job_id="job-007")
        assert len(result.modules) == 2
        assert result.modules[0].module_number == 1
        assert result.modules[1].module_number == 2

    def test_multiple_passages_per_module(self):
        """Module with 2 different passages produces 2 passage blocks."""
        questions = [
            _make_question_record(module_number=1, slot_number=1, passage_id="p-a"),
            _make_question_record(
                module_number=1, slot_number=2, passage_id="p-b",
                skill_type=SkillType.PUNCTUATION, difficulty=Difficulty.MEDIUM,
            ),
        ]
        blueprint = _make_blueprint()
        result = assemble_test(questions, blueprint, job_id="job-008")
        mod1 = result.modules[0]
        assert len(mod1.passages) == 2
        assert {pb.passage_id for pb in mod1.passages} == {"p-a", "p-b"}

    def test_skill_distribution_warning(self, caplog):
        """Warning logged when a blueprint skill_type has zero questions."""
        caplog.set_level(0)  # capture everything
        questions = [
            _make_question_record(
                module_number=1, slot_number=1, passage_id="p1",
                skill_type=SkillType.SENTENCE_FORMATION,
            ),
        ]
        blueprint = _make_blueprint()
        # Blueprint has PUNCTUATION in module 1 slot 2 — no question uses it
        assemble_test(questions, blueprint, job_id="job-009")
        assert any("Missing skill type" in str(rec) for rec in caplog.records)

    def test_difficulty_distribution_warning(self, caplog):
        """Warning logged when difficulty deviates >10 % from blueprint."""
        caplog.set_level(0)  # capture everything
        # Blueprint expects 40 % easy / 20 % medium / 40 % hard
        # We give 100 % easy → large deviation on medium & hard
        questions = [
            _make_question_record(
                module_number=1, slot_number=1, passage_id="p1",
                difficulty=Difficulty.EASY,
            ),
            _make_question_record(
                module_number=1, slot_number=2, passage_id="p1",
                skill_type=SkillType.PUNCTUATION, difficulty=Difficulty.EASY,
            ),
        ]
        blueprint = _make_blueprint()
        assemble_test(questions, blueprint, job_id="job-010")
        assert any("Difficulty mismatch" in str(rec) for rec in caplog.records)


class TestSaveTest:
    """Tests for ``save_test``."""

    @pytest.mark.asyncio
    async def test_save_test_calls_save_inventory_record(self):
        """``save_test`` delegates to ``save_inventory_record``."""
        blueprint = _make_blueprint()
        questions = [
            _make_question_record(module_number=1, slot_number=1, passage_id="p1"),
        ]
        test = assemble_test(questions, blueprint, job_id="job-011")

        with patch(
            "backend.app.generation.assembler.save_inventory_record",
            new=AsyncMock(),
        ) as mock_save:
            await save_test(test)
            mock_save.assert_awaited_once_with(test)
