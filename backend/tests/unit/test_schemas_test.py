"""Unit tests for backend.app.schemas.test — ModuleSlot, ModuleConfig, TestBlueprint, GeneratedModule, GeneratedTest."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.enums import Difficulty, SkillType
from backend.app.schemas.question import AnswerChoice, GeneratedQuestion, GeneratedPassageBlock
from backend.app.schemas.enums import DistractorRole
from backend.app.schemas.test import (
    GeneratedModule,
    GeneratedTest,
    ModuleConfig,
    ModuleSlot,
    TestBlueprint,
)


# ── Helpers ──────────────────────────────────────────────────

def _valid_choice(letter: str, role: DistractorRole) -> AnswerChoice:
    return AnswerChoice(letter=letter, text=f"Choice {letter}", distractor_role=role)


def _valid_choices():
    return [
        _valid_choice("A", DistractorRole.BEST_ANSWER),
        _valid_choice("B", DistractorRole.GOOD_NOT_BEST),
        _valid_choice("C", DistractorRole.COMPLETELY_WRONG),
        _valid_choice("D", DistractorRole.COMPLETELY_WRONG),
    ]


def _valid_question(**overrides) -> dict:
    base = {
        "id": "q-001",
        "passage_id": "p-001",
        "module_number": 1,
        "slot_number": 1,
        "question_number": 1,
        "question_text": "What is the answer?",
        "choices": _valid_choices(),
        "correct_answer": "A",
        "explanation": "A is correct.",
        "supporting_line": "Line 5",
        "skill_type": SkillType.RHETORIC,
        "difficulty": Difficulty.MEDIUM,
    }
    base.update(overrides)
    return base


def _valid_slot(**overrides) -> dict:
    base = {
        "slot_number": 1,
        "skill_type": SkillType.RHETORIC,
        "difficulty": Difficulty.MEDIUM,
        "question_count": 5,
    }
    base.update(overrides)
    return base


# ── ModuleSlot ────────────────────────────────────────────────

def test_module_slot_creation():
    s = ModuleSlot(**_valid_slot())
    assert s.slot_number == 1
    assert s.skill_type == SkillType.RHETORIC
    assert s.difficulty == Difficulty.MEDIUM
    assert s.question_count == 5
    assert s.has_figure is False
    assert s.figure_data is None


def test_module_slot_slot_number_ge1():
    s = ModuleSlot(**_valid_slot(slot_number=1))
    assert s.slot_number == 1


def test_module_slot_slot_number_zero_invalid():
    with pytest.raises(ValidationError):
        ModuleSlot(**_valid_slot(slot_number=0))


def test_module_slot_slot_number_negative_invalid():
    with pytest.raises(ValidationError):
        ModuleSlot(**_valid_slot(slot_number=-1))


def test_module_slot_question_count_ge1():
    s = ModuleSlot(**_valid_slot(question_count=1))
    assert s.question_count == 1


def test_module_slot_question_count_zero_invalid():
    with pytest.raises(ValidationError):
        ModuleSlot(**_valid_slot(question_count=0))


def test_module_slot_has_figure_default_false():
    s = ModuleSlot(**_valid_slot())
    assert s.has_figure is False


def test_module_slot_has_figure_explicit_true():
    s = ModuleSlot(**_valid_slot(has_figure=True))
    assert s.has_figure is True


def test_module_slot_figure_data_default_none():
    s = ModuleSlot(**_valid_slot())
    assert s.figure_data is None


def test_module_slot_figure_data_explicit():
    s = ModuleSlot(**_valid_slot(figure_data="base64image"))
    assert s.figure_data == "base64image"


# ── ModuleConfig ──────────────────────────────────────────────

def test_module_config_creation():
    slot = ModuleSlot(**_valid_slot())
    mc = ModuleConfig(module_number=1, module_type="reading_long", slots=[slot])
    assert mc.module_number == 1
    assert mc.module_type == "reading_long"
    assert mc.slots == [slot]


def test_module_config_question_count_property():
    s1 = ModuleSlot(**_valid_slot(question_count=5))
    s2 = ModuleSlot(**_valid_slot(slot_number=2, question_count=3))
    mc = ModuleConfig(module_number=1, module_type="writing", slots=[s1, s2])
    assert mc.question_count == 8


def test_module_config_question_count_single_slot():
    s = ModuleSlot(**_valid_slot(question_count=7))
    mc = ModuleConfig(module_number=1, module_type="writing", slots=[s])
    assert mc.question_count == 7


def test_module_config_module_number_ge1_le3():
    for mn in [1, 2, 3]:
        mc = ModuleConfig(module_number=mn, module_type="writing", slots=[ModuleSlot(**_valid_slot())])
        assert mc.module_number == mn


def test_module_config_module_number_zero_invalid():
    with pytest.raises(ValidationError):
        ModuleConfig(module_number=0, module_type="writing", slots=[ModuleSlot(**_valid_slot())])


def test_module_config_module_number_four_invalid():
    with pytest.raises(ValidationError):
        ModuleConfig(module_number=4, module_type="writing", slots=[ModuleSlot(**_valid_slot())])


def test_module_config_slots_min_length_1():
    with pytest.raises(ValidationError):
        ModuleConfig(module_number=1, module_type="writing", slots=[])


def test_module_config_has_figure_default_false():
    mc = ModuleConfig(module_number=1, module_type="writing", slots=[ModuleSlot(**_valid_slot())])
    assert mc.has_figure is False


def test_module_config_wordy_answer_style_default_false():
    mc = ModuleConfig(module_number=1, module_type="writing", slots=[ModuleSlot(**_valid_slot())])
    assert mc.wordy_answer_style is False


# ── TestBlueprint ────────────────────────────────────────────

def test_test_blueprint_creation():
    slot = ModuleSlot(**_valid_slot())
    mc = ModuleConfig(module_number=1, module_type="reading_long", slots=[slot])
    bp = TestBlueprint(
        id="bp-001",
        name="DEFAULT_BLUEPRINT",
        modules=[mc],
        total_questions=5,
        difficulty_distribution={"easy": 0.3, "medium": 0.4, "hard": 0.3},
    )
    assert bp.id == "bp-001"
    assert bp.name == "DEFAULT_BLUEPRINT"
    assert len(bp.modules) == 1
    assert bp.total_questions == 5


def test_test_blueprint_total_questions_ge0():
    bp = TestBlueprint(
        id="bp-001",
        name="test",
        modules=[ModuleConfig(module_number=1, module_type="writing", slots=[ModuleSlot(**_valid_slot())])],
        total_questions=0,
        difficulty_distribution={"easy": 0.3, "medium": 0.4, "hard": 0.3},
    )
    assert bp.total_questions == 0


def test_test_blueprint_total_questions_negative_invalid():
    with pytest.raises(ValidationError):
        TestBlueprint(
            id="bp-001",
            name="test",
            modules=[ModuleConfig(module_number=1, module_type="writing", slots=[ModuleSlot(**_valid_slot())])],
            total_questions=-1,
            difficulty_distribution={"easy": 0.3, "medium": 0.4, "hard": 0.3},
        )


def test_test_blueprint_modules_min_length_1():
    with pytest.raises(ValidationError):
        TestBlueprint(
            id="bp-001",
            name="test",
            modules=[],
            total_questions=0,
            difficulty_distribution={"easy": 0.3, "medium": 0.4, "hard": 0.3},
        )


def test_test_blueprint_repr():
    bp = TestBlueprint(
        id="bp-001",
        name="DEFAULT_BLUEPRINT",
        modules=[ModuleConfig(module_number=1, module_type="writing", slots=[ModuleSlot(**_valid_slot())])],
        total_questions=5,
        difficulty_distribution={"easy": 0.3, "medium": 0.4, "hard": 0.3},
    )
    r = repr(bp)
    assert "TestBlueprint" in r
    assert "DEFAULT_BLUEPRINT" in r
    assert "total_questions=5" in r


# ── GeneratedModule ──────────────────────────────────────────

def test_generated_module_creation():
    q = GeneratedQuestion(**_valid_question())
    pb = GeneratedPassageBlock(passage_id="p-001", passage_text="Text", questions=[q])
    gm = GeneratedModule(
        module_number=1,
        module_type="reading_long",
        passages=[pb],
        questions=[q],
        question_count=1,
    )
    assert gm.module_number == 1
    assert gm.module_type == "reading_long"
    assert gm.question_count == 1


def test_generated_module_repr():
    q = GeneratedQuestion(**_valid_question())
    pb = GeneratedPassageBlock(passage_id="p-001", passage_text="Text", questions=[q])
    gm = GeneratedModule(
        module_number=2,
        module_type="reading_short",
        passages=[pb],
        questions=[q],
        question_count=1,
    )
    r = repr(gm)
    assert "GeneratedModule" in r
    assert "module_number=2" in r
    assert "module_type='reading_short'" in r
    assert "questions=1" in r


def test_generated_module_question_count_ge0():
    q = GeneratedQuestion(**_valid_question())
    pb = GeneratedPassageBlock(passage_id="p-001", passage_text="Text", questions=[q])
    gm = GeneratedModule(
        module_number=1,
        module_type="writing",
        passages=[pb],
        questions=[q],
        question_count=0,
    )
    assert gm.question_count == 0


# ── GeneratedTest ────────────────────────────────────────────

def test_generated_test_creation():
    q = GeneratedQuestion(**_valid_question())
    pb = GeneratedPassageBlock(passage_id="p-001", passage_text="Text", questions=[q])
    gm = GeneratedModule(
        module_number=1,
        module_type="reading_long",
        passages=[pb],
        questions=[q],
        question_count=1,
    )
    gt = GeneratedTest(
        id="t-001",
        job_id="j-001",
        blueprint_id="bp-001",
        questions=[q],
        modules=[gm],
        total_questions=1,
    )
    assert gt.id == "t-001"
    assert gt.job_id == "j-001"
    assert gt.total_questions == 1


def test_generated_test_repr():
    q = GeneratedQuestion(**_valid_question())
    pb = GeneratedPassageBlock(passage_id="p-001", passage_text="Text", questions=[q])
    gm = GeneratedModule(
        module_number=1,
        module_type="reading_long",
        passages=[pb],
        questions=[q],
        question_count=1,
    )
    gt = GeneratedTest(
        id="t-001",
        job_id="j-001",
        blueprint_id="bp-001",
        questions=[q],
        modules=[gm],
        total_questions=1,
    )
    r = repr(gt)
    assert "GeneratedTest" in r
    assert "total_questions=1" in r
    assert "modules=1" in r


def test_generated_test_optional_pdf_paths():
    q = GeneratedQuestion(**_valid_question())
    pb = GeneratedPassageBlock(passage_id="p-001", passage_text="Text", questions=[q])
    gm = GeneratedModule(
        module_number=1,
        module_type="reading_long",
        passages=[pb],
        questions=[q],
        question_count=1,
    )
    gt = GeneratedTest(
        id="t-001",
        job_id="j-001",
        blueprint_id="bp-001",
        questions=[q],
        modules=[gm],
        total_questions=1,
    )
    assert gt.student_pdf_path is None
    assert gt.teacher_pdf_path is None


def test_generated_test_created_at_auto_populates():
    q = GeneratedQuestion(**_valid_question())
    pb = GeneratedPassageBlock(passage_id="p-001", passage_text="Text", questions=[q])
    gm = GeneratedModule(
        module_number=1,
        module_type="reading_long",
        passages=[pb],
        questions=[q],
        question_count=1,
    )
    gt = GeneratedTest(
        id="t-001",
        job_id="j-001",
        blueprint_id="bp-001",
        questions=[q],
        modules=[gm],
        total_questions=1,
    )
    assert gt.created_at is not None
    assert gt.created_at.tzinfo is not None


def test_generated_test_strict_allows_extra_fields():
    """strict=True enforces strict types but does NOT forbid extra fields."""
    q = GeneratedQuestion(**_valid_question())
    pb = GeneratedPassageBlock(passage_id="p-001", passage_text="Text", questions=[q])
    gm = GeneratedModule(
        module_number=1,
        module_type="reading_long",
        passages=[pb],
        questions=[q],
        question_count=1,
    )
    gt = GeneratedTest(
        id="t-001",
        job_id="j-001",
        blueprint_id="bp-001",
        questions=[q],
        modules=[gm],
        total_questions=1,
        extra_field="ignored",
    )
    assert gt.id == "t-001"
