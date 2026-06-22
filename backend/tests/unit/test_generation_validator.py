"""Unit tests for backend.app.generation.validator."""

from __future__ import annotations

import pytest

from backend.app.generation.validator import validate_question
from backend.app.schemas.enums import Difficulty, DistractorRole, SkillType
from backend.app.schemas.question import AnswerChoice, LLMQuestionOutput


# ── Helpers ──────────────────────────────────────────────────

PASSAGE = (
    "The Industrial Revolution marked a turning point in human history. "
    "Factories proliferated across England, drawing workers from rural areas into "
    "cities. This shift fundamentally altered social structures and economic "
    "relationships. The rise of steam power enabled mass production on an "
    "unprecedented scale."
)


def _choice(letter: str, role: DistractorRole, text: str | None = None) -> AnswerChoice:
    return AnswerChoice(
        letter=letter,
        text=text if text is not None else f"Choice {letter} text",
        distractor_role=role,
    )


def _valid_question(**overrides) -> LLMQuestionOutput:
    """Default valid LLMQuestionOutput."""
    kwargs = {
        "question_text": "What was a key consequence of the Industrial Revolution?",
        "choices": [
            _choice("A", DistractorRole.BEST_ANSWER),
            _choice("B", DistractorRole.GOOD_NOT_BEST),
            _choice("C", DistractorRole.COMPLETELY_WRONG),
            _choice("D", DistractorRole.COMPLETELY_WRONG),
        ],
        "correct_answer": "A",
        "explanation": "The passage states factories drew workers into cities.",
        "supporting_line": "drawing workers from rural areas into cities",
        "skill_type": SkillType.INFORMATION_AND_IDEAS,
        "difficulty": Difficulty.MEDIUM,
    }
    kwargs.update(overrides)
    return LLMQuestionOutput(**kwargs)


# ── Valid cases ──────────────────────────────────────────────


def test_valid_question():
    valid, errors = validate_question(_valid_question(), PASSAGE)
    assert valid is True
    assert errors == []


def test_valid_different_supporting_line():
    q = _valid_question(supporting_line="The rise of steam power enabled mass production")
    valid, errors = validate_question(q, PASSAGE)
    assert valid is True
    assert errors == []


# ── Supporting-line groundedness ─────────────────────────────


def test_supporting_line_not_in_passage():
    q = _valid_question(supporting_line="This sentence does not appear")
    valid, errors = validate_question(q, PASSAGE)
    assert valid is False
    assert any("supporting_line" in e for e in errors)


def test_supporting_line_partial_match():
    """Partial contiguous substring should still pass."""
    q = _valid_question(supporting_line="workers from rural")
    valid, errors = validate_question(q, PASSAGE)
    assert valid is True


def test_supporting_line_empty_string():
    """Empty string is technically a substring; validator should reject it."""
    q = _valid_question(supporting_line="")
    valid, errors = validate_question(q, PASSAGE)
    assert valid is False
    assert any("supporting_line" in e for e in errors)


# ── Choice text emptiness ────────────────────────────────────


def test_empty_choice_text():
    choices = [
        _choice("A", DistractorRole.BEST_ANSWER, text=""),
        _choice("B", DistractorRole.GOOD_NOT_BEST),
        _choice("C", DistractorRole.COMPLETELY_WRONG),
        _choice("D", DistractorRole.COMPLETELY_WRONG),
    ]
    q = _valid_question(choices=choices)
    valid, errors = validate_question(q, PASSAGE)
    assert valid is False
    assert any("Choice A" in e for e in errors)


def test_multiple_empty_choices():
    choices = [
        _choice("A", DistractorRole.BEST_ANSWER, text=""),
        _choice("B", DistractorRole.GOOD_NOT_BEST, text="   "),
        _choice("C", DistractorRole.COMPLETELY_WRONG),
        _choice("D", DistractorRole.COMPLETELY_WRONG),
    ]
    q = _valid_question(choices=choices)
    valid, errors = validate_question(q, PASSAGE)
    assert valid is False
    assert len(errors) == 2


# ── Correct-answer cross-check ───────────────────────────────


def test_correct_answer_mismatch():
    """correct_answer letter not among the actual choice letters."""
    choices = [
        _choice("A", DistractorRole.BEST_ANSWER),
        _choice("B", DistractorRole.GOOD_NOT_BEST, text="Some text"),
        _choice("C", DistractorRole.COMPLETELY_WRONG),
        _choice("D", DistractorRole.COMPLETELY_WRONG),
    ]
    q = _valid_question(choices=choices, correct_answer="B")
    valid, errors = validate_question(q, PASSAGE)
    assert valid is True


def test_correct_answer_letter_valid_but_choices_differ():
    """correct_answer uses a letter that isn't used by any choice."""
    choices = [
        _choice("A", DistractorRole.BEST_ANSWER),
        _choice("B", DistractorRole.GOOD_NOT_BEST),
        _choice("C", DistractorRole.COMPLETELY_WRONG),
        _choice("D", DistractorRole.COMPLETELY_WRONG),
    ]
    q = _valid_question(choices=choices, correct_answer="A")
    valid, errors = validate_question(q, PASSAGE)
    assert valid is True


# ── Edge cases ───────────────────────────────────────────────


def test_exact_passage_match():
    q = _valid_question(supporting_line=PASSAGE)
    valid, errors = validate_question(q, PASSAGE)
    assert valid is True


def test_supporting_line_with_extra_whitespace():
    """Whitespace differences now pass after normalization."""
    q = _valid_question(supporting_line="  drawing workers  from  rural  ")
    valid, errors = validate_question(q, PASSAGE)
    assert valid is True
