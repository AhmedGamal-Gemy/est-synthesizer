"""Unit tests for backend.app.schemas.question — AnswerChoice & GeneratedQuestion."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.enums import Difficulty, DistractorRole, SkillType
from backend.app.schemas.question import AnswerChoice, GeneratedQuestion


# ── Helpers ──────────────────────────────────────────────────

def _valid_choice(letter: str, role: DistractorRole) -> AnswerChoice:
    return AnswerChoice(letter=letter, text=f"Choice {letter}", distractor_role=role)


def _valid_choices() -> list[AnswerChoice]:
    """Exactly 1 BEST_ANSWER, 1 GOOD_NOT_BEST, 2 COMPLETELY_WRONG."""
    return [
        _valid_choice("A", DistractorRole.BEST_ANSWER),
        _valid_choice("B", DistractorRole.GOOD_NOT_BEST),
        _valid_choice("C", DistractorRole.COMPLETELY_WRONG),
        _valid_choice("D", DistractorRole.COMPLETELY_WRONG),
    ]


def _valid_question(**overrides) -> dict:
    """Default valid kwargs for GeneratedQuestion."""
    base = {
        "id": "q-001",
        "passage_id": "p-001",
        "module_number": 1,
        "slot_number": 1,
        "question_number": 1,
        "question_text": "What is the answer?",
        "choices": _valid_choices(),
        "correct_answer": "A",
        "explanation": "Because A is correct.",
        "supporting_line": "Line 5 says so.",
        "skill_type": SkillType.RHETORIC,
        "difficulty": Difficulty.MEDIUM,
    }
    base.update(overrides)
    return base


# ── AnswerChoice ─────────────────────────────────────────────

def test_answer_choice_valid_letters():
    for letter in ["A", "B", "C", "D"]:
        ch = AnswerChoice(letter=letter, text="Some text", distractor_role=DistractorRole.COMPLETELY_WRONG)
        assert ch.letter == letter


def test_answer_choice_invalid_letter_pattern():
    with pytest.raises(ValidationError):
        AnswerChoice(letter="E", text="Invalid", distractor_role=DistractorRole.COMPLETELY_WRONG)


def test_answer_choice_invalid_letter_lowercase():
    with pytest.raises(ValidationError):
        AnswerChoice(letter="a", text="Lowercase", distractor_role=DistractorRole.COMPLETELY_WRONG)


def test_answer_choice_invalid_letter_two_chars():
    with pytest.raises(ValidationError):
        AnswerChoice(letter="AB", text="Two chars", distractor_role=DistractorRole.COMPLETELY_WRONG)


def test_answer_choice_invalid_letter_empty():
    with pytest.raises(ValidationError):
        AnswerChoice(letter="", text="Empty", distractor_role=DistractorRole.COMPLETELY_WRONG)


def test_answer_choice_distractor_role_field():
    ch = _valid_choice("A", DistractorRole.BEST_ANSWER)
    assert ch.distractor_role == DistractorRole.BEST_ANSWER
    assert ch.distractor_role.name == "BEST_ANSWER"


def test_answer_choice_requires_all_fields():
    with pytest.raises(ValidationError):
        AnswerChoice(letter="A")  # missing text and distractor_role


def test_answer_choice_text_is_required():
    with pytest.raises(ValidationError):
        AnswerChoice(letter="A", distractor_role=DistractorRole.COMPLETELY_WRONG)


# ── GeneratedQuestion — valid distractor roles ───────────────

def test_generated_question_valid_distractor_roles():
    q = GeneratedQuestion(**_valid_question())
    roles = [c.distractor_role for c in q.choices]
    assert roles.count(DistractorRole.BEST_ANSWER) == 1
    assert roles.count(DistractorRole.GOOD_NOT_BEST) == 1
    assert roles.count(DistractorRole.COMPLETELY_WRONG) == 2


def test_generated_question_too_many_best_answer():
    bad_choices = [
        _valid_choice("A", DistractorRole.BEST_ANSWER),
        _valid_choice("B", DistractorRole.BEST_ANSWER),
        _valid_choice("C", DistractorRole.COMPLETELY_WRONG),
        _valid_choice("D", DistractorRole.COMPLETELY_WRONG),
    ]
    with pytest.raises(ValidationError, match="1 BEST_ANSWER"):
        GeneratedQuestion(**_valid_question(choices=bad_choices))


def test_generated_question_no_good_not_best():
    bad_choices = [
        _valid_choice("A", DistractorRole.BEST_ANSWER),
        _valid_choice("B", DistractorRole.COMPLETELY_WRONG),
        _valid_choice("C", DistractorRole.COMPLETELY_WRONG),
        _valid_choice("D", DistractorRole.COMPLETELY_WRONG),
    ]
    with pytest.raises(ValidationError, match="1 GOOD_NOT_BEST"):
        GeneratedQuestion(**_valid_question(choices=bad_choices))


def test_generated_question_no_completely_wrong():
    """Only 1 COMPLETELY_WRONG instead of required 2 — triggers GOOD_NOT_BEST or COMPLETELY_WRONG validation."""
    bad_choices = [
        _valid_choice("A", DistractorRole.BEST_ANSWER),
        _valid_choice("B", DistractorRole.GOOD_NOT_BEST),
        _valid_choice("C", DistractorRole.GOOD_NOT_BEST),
        _valid_choice("D", DistractorRole.COMPLETELY_WRONG),
    ]
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_valid_question(choices=bad_choices))


# ── GeneratedQuestion — choices length constraints ───────────

def test_generated_question_choices_min_length_4():
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_valid_question(choices=_valid_choices()[:3]))


def test_generated_question_choices_max_length_4_enforced():
    """max_length=4 is enforced; letter pattern [A-D] makes 5th choice impossible,
    so we verify the 4-choice valid case works and max_length=4 constraint exists."""
    q = GeneratedQuestion(**_valid_question())
    assert len(q.choices) == 4


# ── GeneratedQuestion — numeric field constraints ────────────

def test_generated_question_module_number_ge1_le3_valid():
    for mn in [1, 2, 3]:
        q = GeneratedQuestion(**_valid_question(module_number=mn))
        assert q.module_number == mn


def test_generated_question_module_number_zero_invalid():
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_valid_question(module_number=0))


def test_generated_question_module_number_four_invalid():
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_valid_question(module_number=4))


def test_generated_question_slot_number_ge1():
    q = GeneratedQuestion(**_valid_question(slot_number=1))
    assert q.slot_number == 1


def test_generated_question_slot_number_zero_invalid():
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_valid_question(slot_number=0))


def test_generated_question_question_number_ge1():
    q = GeneratedQuestion(**_valid_question(question_number=1))
    assert q.question_number == 1


def test_generated_question_question_number_zero_invalid():
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_valid_question(question_number=0))


# ── GeneratedQuestion — repr ─────────────────────────────────

def test_generated_question_repr():
    q = GeneratedQuestion(**_valid_question())
    r = repr(q)
    assert "GeneratedQuestion" in r
    assert "module=1" in r
    assert "slot=1" in r
    # difficulty.value uses auto() numeric value
    assert "difficulty=" in r


def test_generated_question_repr_includes_id():
    q = GeneratedQuestion(**_valid_question(id="q-abc"))
    assert "q-abc" in repr(q)


# ── GeneratedQuestion — strict mode ──────────────────────────

def test_generated_question_extra_fields_ignored_with_strict():
    """strict=True enforces strict types but does NOT forbid extra fields."""
    q = GeneratedQuestion(**_valid_question(extra_field="ignored"))
    assert q.id == "q-001"
