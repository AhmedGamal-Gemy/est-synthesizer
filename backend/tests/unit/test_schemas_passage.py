"""Unit tests for backend.app.schemas.passage — Passage model."""

import pytest
from datetime import datetime, timezone

from pydantic import ValidationError

from backend.app.schemas.enums import PassageCategory, PassageType
from backend.app.schemas.passage import Figure, Passage


# ── Helpers ──────────────────────────────────────────────────

def _valid_passage(**overrides) -> dict:
    base = {
        "id": "p-001",
        "text": "A sample passage text for testing purposes.",
        "source_url": "https://example.com/passage1",
        "source_title": "Example Passage",
        "passage_type": PassageType.LONG,
        "passage_category": PassageCategory.ESSAY,
        "word_count": 50,
        "reading_level": 8.5,
    }
    base.update(overrides)
    return base


# ── Passage — creation with required fields ──────────────────

def test_passage_creation_with_required_fields():
    p = Passage(**_valid_passage())
    assert p.id == "p-001"
    assert p.text == "A sample passage text for testing purposes."
    assert p.source_url == "https://example.com/passage1"
    assert p.source_title == "Example Passage"
    assert p.passage_type == PassageType.LONG
    assert p.passage_category == PassageCategory.ESSAY
    assert p.word_count == 50
    assert p.reading_level == 8.5


def test_passage_missing_required_field():
    for missing_field in ["id", "text", "source_url", "source_title", "passage_type", "passage_category", "word_count", "reading_level"]:
        kwargs = _valid_passage()
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            Passage(**kwargs)


# ── Passage — word_count ge=0 ────────────────────────────────

def test_passage_word_count_zero_valid():
    p = Passage(**_valid_passage(word_count=0))
    assert p.word_count == 0


def test_passage_word_count_positive_valid():
    p = Passage(**_valid_passage(word_count=500))
    assert p.word_count == 500


def test_passage_word_count_negative_invalid():
    with pytest.raises(ValidationError):
        Passage(**_valid_passage(word_count=-1))


# ── Passage — embedding default=None ─────────────────────────

def test_passage_embedding_default_none():
    p = Passage(**_valid_passage())
    assert p.embedding is None


def test_passage_embedding_explicit_list():
    p = Passage(**_valid_passage(embedding=[0.1, 0.2, 0.3]))
    assert p.embedding == [0.1, 0.2, 0.3]


# ── Passage — last_used_at default=None ──────────────────────

def test_passage_last_used_at_default_none():
    p = Passage(**_valid_passage())
    assert p.last_used_at is None


def test_passage_last_used_at_explicit_datetime():
    dt = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    p = Passage(**_valid_passage(last_used_at=dt))
    assert p.last_used_at == dt


# ── Passage — created_at auto-populates UTC ──────────────────

def test_passage_created_at_auto_populates():
    p = Passage(**_valid_passage())
    assert p.created_at is not None
    # Verify timezone-aware UTC
    assert p.created_at.tzinfo is not None


def test_passage_created_at_explicit_value():
    dt = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    p = Passage(**_valid_passage(created_at=dt))
    assert p.created_at == dt


# ── Passage — enum field acceptance ──────────────────────────

def test_passage_passage_type_accepts_enum():
    for pt in PassageType:
        p = Passage(**_valid_passage(passage_type=pt))
        assert p.passage_type == pt


def test_passage_passage_category_accepts_enum():
    for cat in PassageCategory:
        p = Passage(**_valid_passage(passage_category=cat))
        assert p.passage_category == cat


def test_passage_passage_type_strict_rejects_string():
    """strict=True requires actual enum instances, not string values."""
    with pytest.raises(ValidationError):
        Passage(**_valid_passage(passage_type="long"))


def test_passage_passage_category_strict_rejects_string():
    """strict=True requires actual enum instances, not string values."""
    with pytest.raises(ValidationError):
        Passage(**_valid_passage(passage_category="essay"))


# ── Passage — repr ───────────────────────────────────────────

def test_passage_repr():
    p = Passage(**_valid_passage())
    r = repr(p)
    assert "Passage" in r
    assert "word_count=50" in r


def test_passage_repr_includes_id():
    p = Passage(**_valid_passage(id="p-abc"))
    assert "p-abc" in repr(p)


# ── Passage — strict mode ────────────────────────────────────

def test_passage_extra_fields_ignored_with_strict():
    """strict=True enforces strict types but does NOT forbid extra fields."""
    p = Passage(**_valid_passage(extra_field="ignored"))
    assert p.id == "p-001"


# ── Figure ────────────────────────────────────────────────────


def test_figure_creation_with_required_fields():
    f = Figure(caption="Chart 1", description="A bar chart showing results")
    assert f.caption == "Chart 1"
    assert f.description == "A bar chart showing results"
    assert f.data is None


def test_figure_creation_with_optional_data():
    f = Figure(caption="Chart 1", description="A bar chart showing results", data="base64image")
    assert f.data == "base64image"


def test_figure_missing_required_caption():
    with pytest.raises(ValidationError):
        Figure(description="A description")


def test_figure_missing_required_description():
    with pytest.raises(ValidationError):
        Figure(caption="A caption")


def test_figure_strict_mode():
    """strict=True enforces strict types."""
    f = Figure(caption="Chart 1", description="A bar chart", data="url")
    assert f.caption == "Chart 1"


# ── Passage — figure field ────────────────────────────────────


def test_passage_figure_default_none():
    p = Passage(**_valid_passage())
    assert p.figure is None


def test_passage_with_figure():
    f = Figure(caption="Chart 1", description="A bar chart showing results")
    p = Passage(**_valid_passage(figure=f))
    assert p.figure is not None
    assert p.figure.caption == "Chart 1"
    assert p.figure.description == "A bar chart showing results"


def test_passage_with_figure_and_data():
    f = Figure(caption="Chart 1", description="A bar chart", data="base64image")
    p = Passage(**_valid_passage(figure=f))
    assert p.figure.data == "base64image"


def test_passage_repr_without_figure():
    p = Passage(**_valid_passage())
    r = repr(p)
    assert "figure" not in r


def test_passage_repr_with_figure():
    f = Figure(caption="Chart 1", description="A bar chart")
    p = Passage(**_valid_passage(figure=f))
    r = repr(p)
    assert "figure=True" in r
