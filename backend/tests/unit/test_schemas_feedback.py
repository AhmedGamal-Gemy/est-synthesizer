"""Unit tests for backend.app.schemas.feedback — QuestionFeedback model."""

import pytest
from datetime import datetime, timezone

from pydantic import ValidationError

from backend.app.schemas.enums import QuestionFlag
from backend.app.schemas.feedback import QuestionFeedback


# ── Helpers ──────────────────────────────────────────────────

def _valid_feedback(**overrides) -> dict:
    base = {
        "id": "f-001",
        "test_id": "t-001",
        "question_id": "q-001",
        "rating": 3,
        "flags": [QuestionFlag.AMBIGUOUS],
    }
    base.update(overrides)
    return base


# ── QuestionFeedback — creation ──────────────────────────────

def test_question_feedback_creation():
    fb = QuestionFeedback(**_valid_feedback())
    assert fb.id == "f-001"
    assert fb.test_id == "t-001"
    assert fb.question_id == "q-001"
    assert fb.rating == 3
    assert fb.flags == [QuestionFlag.AMBIGUOUS]


def test_question_feedback_missing_required_field():
    for missing in ["id", "test_id", "question_id", "rating", "flags"]:
        kwargs = _valid_feedback()
        del kwargs[missing]
        with pytest.raises(ValidationError):
            QuestionFeedback(**kwargs)


# ── QuestionFeedback — rating ge=1 le=5 ──────────────────────

def test_question_feedback_rating_valid_boundaries():
    for rating in [1, 2, 3, 4, 5]:
        fb = QuestionFeedback(**_valid_feedback(rating=rating))
        assert fb.rating == rating


def test_question_feedback_rating_zero_invalid():
    with pytest.raises(ValidationError):
        QuestionFeedback(**_valid_feedback(rating=0))


def test_question_feedback_rating_six_invalid():
    with pytest.raises(ValidationError):
        QuestionFeedback(**_valid_feedback(rating=6))


def test_question_feedback_rating_negative_invalid():
    with pytest.raises(ValidationError):
        QuestionFeedback(**_valid_feedback(rating=-1))


# ── QuestionFeedback — flags accepts list of QuestionFlag ────

def test_question_feedback_flags_single_flag():
    fb = QuestionFeedback(**_valid_feedback(flags=[QuestionFlag.OFF_TOPIC]))
    assert fb.flags == [QuestionFlag.OFF_TOPIC]


def test_question_feedback_flags_multiple_flags():
    flags = [QuestionFlag.AMBIGUOUS, QuestionFlag.TOO_EASY, QuestionFlag.UNCLEAR_DISTRACTORS]
    fb = QuestionFeedback(**_valid_feedback(flags=flags))
    assert fb.flags == flags


def test_question_feedback_flags_empty_list():
    # flags field has no min_length, so empty list should be valid
    fb = QuestionFeedback(**_valid_feedback(flags=[]))
    assert fb.flags == []


def test_question_feedback_flags_strict_rejects_string():
    """strict=True requires actual enum instances, not string values."""
    with pytest.raises(ValidationError):
        QuestionFeedback(**_valid_feedback(flags=["ambiguous"]))


# ── QuestionFeedback — notes default=None ────────────────────

def test_question_feedback_notes_default_none():
    fb = QuestionFeedback(**_valid_feedback())
    assert fb.notes is None


def test_question_feedback_notes_explicit():
    fb = QuestionFeedback(**_valid_feedback(notes="This question is confusing"))
    assert fb.notes == "This question is confusing"


# ── QuestionFeedback — created_at auto-populates ─────────────

def test_question_feedback_created_at_auto_populates():
    fb = QuestionFeedback(**_valid_feedback())
    assert fb.created_at is not None
    assert fb.created_at.tzinfo is not None


def test_question_feedback_created_at_explicit():
    dt = datetime(2025, 3, 15, 10, 0, tzinfo=timezone.utc)
    fb = QuestionFeedback(**_valid_feedback(created_at=dt))
    assert fb.created_at == dt


# ── QuestionFeedback — repr ──────────────────────────────────

def test_question_feedback_repr():
    fb = QuestionFeedback(**_valid_feedback())
    r = repr(fb)
    assert "QuestionFeedback" in r
    assert "rating=3" in r


def test_question_feedback_repr_includes_ids():
    fb = QuestionFeedback(**_valid_feedback(id="f-abc", test_id="t-xyz"))
    r = repr(fb)
    assert "f-abc" in r
    assert "t-xyz" in r


# ── QuestionFeedback — strict mode ───────────────────────────

def test_question_feedback_extra_fields_ignored_with_strict():
    """strict=True enforces strict types but does NOT forbid extra fields."""
    fb = QuestionFeedback(**_valid_feedback(extra_field="ignored"))
    assert fb.id == "f-001"
