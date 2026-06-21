"""Unit tests for backend.app.scraper.processor — pure unit tests."""

import uuid
from unittest.mock import patch

import pytest

from backend.app.schemas import Passage, PassageCategory, PassageType
from backend.app.scraper.processor import (
    chunk_text,
    classify_passage_category,
    classify_passage_type,
    compute_reading_level,
    is_suitable,
    process_raw_text,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

# Sample text that textstat will compute a known-ish Flesch-Kincaid score on.
# We use real sentences to ensure textstat processes them properly.
_SAMPLE_TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "This is a simple sentence with common words. "
    "The scientist conducted an experiment in the laboratory. "
    "Data analysis revealed interesting patterns. "
    "The hypothesis was supported by the evidence. "
    "Many species evolve over time through natural selection. "
    "Chemical reactions occur when substances interact. "
    "Biological processes are fundamental to life. "
    "Physics governs the movement of objects in space. "
    "The laboratory experiment demonstrated the theory clearly. "
) * 10  # repeat to get enough length for textstat to work reliably


# ── compute_reading_level ─────────────────────────────────────────────────────


def test_compute_reading_level_returns_score_for_sample_text():
    score = compute_reading_level(_SAMPLE_TEXT)
    assert isinstance(score, float)
    assert score > 0.0


def test_compute_reading_level_returns_zero_for_empty_string():
    assert compute_reading_level("") == 0.0


def test_compute_reading_level_returns_zero_for_whitespace_only():
    assert compute_reading_level("   \n\t  ") == 0.0


def test_compute_reading_level_result_rounded_to_one_decimal():
    score = compute_reading_level(_SAMPLE_TEXT)
    # Check rounding: string representation should have at most 1 decimal place
    decimal_part = str(score).split(".")[-1] if "." in str(score) else "0"
    assert len(decimal_part) <= 1


def test_compute_reading_level_with_mock_textstat():
    """Verify the function calls textstat.flesch_kincaid_grade and rounds."""
    with patch("backend.app.scraper.processor.textstat.flesch_kincaid_grade", return_value=8.456):
        result = compute_reading_level("Some text here that is not empty.")
        assert result == 8.5  # rounded to 1 decimal


# ── classify_passage_type ─────────────────────────────────────────────────────


def test_classify_passage_type_returns_long_for_over_250_words():
    # Generate text with >250 words
    long_text = "word " * 251
    assert classify_passage_type(long_text) == PassageType.LONG


def test_classify_passage_type_returns_short_for_250_words():
    text = "word " * 250
    assert classify_passage_type(text) == PassageType.SHORT


def test_classify_passage_type_returns_short_for_under_250_words():
    short_text = "word " * 100
    assert classify_passage_type(short_text) == PassageType.SHORT


def test_classify_passage_type_accepts_precomputed_word_count():
    # Text is short, but we override with high word_count
    short_text = "short text"
    assert classify_passage_type(short_text, word_count=300) == PassageType.LONG


def test_classify_passage_type_word_count_250_is_short():
    assert classify_passage_type("text", word_count=250) == PassageType.SHORT


def test_classify_passage_type_word_count_251_is_long():
    assert classify_passage_type("text", word_count=251) == PassageType.LONG


# ── classify_passage_category ─────────────────────────────────────────────────


def test_classify_passage_category_returns_scientific_for_science_text():
    text = "experiment study data analysis scientific laboratory observed hypothesis theory species evolution"
    assert classify_passage_category(text) == PassageCategory.SCIENTIFIC


def test_classify_passage_category_returns_history_for_history_text():
    text = "century ancient medieval empire civilization revolution war battle kingdom dynasty historical era reign colony"
    assert classify_passage_category(text) == PassageCategory.HISTORY


def test_classify_passage_category_returns_argumentative_for_argument_text():
    text = "argue debate claim therefore thus consequently objection premise conclusion reasoning however nevertheless opposed assertion"
    # ARGUMENTATIVE has 14 keywords, but tiebreaker ESSAY > NARRATIVE > SCIENTIFIC > HISTORY > ARGUMENTATIVE
    # If ARGUMENTATIVE is the sole max, it wins
    assert classify_passage_category(text) == PassageCategory.ARGUMENTATIVE


def test_classify_passage_category_returns_narrative_for_narrative_text():
    text = "said walked told felt thought story tale character journey adventure castle forest village"
    # NARRATIVE has 13 keywords; ESSAY tiebreaker only kicks in if tied
    assert classify_passage_category(text) == PassageCategory.NARRATIVE


def test_classify_passage_category_returns_essay_for_essay_text():
    text = "essay discourse treatise consideration remark opinion"
    assert classify_passage_category(text) == PassageCategory.ESSAY


def test_classify_passage_category_returns_essay_default_for_no_matching_text():
    text = "random xyzzy qwerty nothing matching any category keywords at all"
    assert classify_passage_category(text) == PassageCategory.ESSAY


def test_classify_passage_category_tiebreaker_essay_wins_over_narrative():
    """When ESSAY and NARRATIVE tie, ESSAY wins per tiebreaker order."""
    # Include exactly 1 ESSAY keyword and 1 NARRATIVE keyword
    text = "essay said"
    result = classify_passage_category(text)
    assert result == PassageCategory.ESSAY


def test_classify_passage_category_tiebreaker_essay_wins_over_scientific():
    """When ESSAY and SCIENTIFIC tie, ESSAY wins."""
    text = "essay experiment"
    result = classify_passage_category(text)
    assert result == PassageCategory.ESSAY


def test_classify_passage_category_tiebreaker_narrative_wins_over_scientific():
    """When NARRATIVE and SCIENTIFIC tie (no ESSAY), NARRATIVE wins."""
    text = "said experiment"
    result = classify_passage_category(text)
    assert result == PassageCategory.NARRATIVE


# ── is_suitable ───────────────────────────────────────────────────────────────


def test_is_suitable_returns_true_for_valid_parameters():
    assert is_suitable(reading_level=10.0, word_count=200, text="Normal text") is True


def test_is_suitable_returns_false_for_reading_level_below_8():
    assert is_suitable(reading_level=7.9, word_count=200, text="Normal text") is False


def test_is_suitable_returns_false_for_reading_level_above_14():
    assert is_suitable(reading_level=14.1, word_count=200, text="Normal text") is False


def test_is_suitable_returns_false_for_word_count_below_80():
    assert is_suitable(reading_level=10.0, word_count=79, text="Normal text") is False


def test_is_suitable_returns_false_for_word_count_above_600():
    assert is_suitable(reading_level=10.0, word_count=601, text="Normal text") is False


def test_is_suitable_returns_true_at_boundary_reading_level_8():
    assert is_suitable(reading_level=8.0, word_count=200, text="Normal text") is True


def test_is_suitable_returns_true_at_boundary_reading_level_14():
    assert is_suitable(reading_level=14.0, word_count=200, text="Normal text") is True


def test_is_suitable_returns_true_at_boundary_word_count_80():
    assert is_suitable(reading_level=10.0, word_count=80, text="Normal text") is True


def test_is_suitable_returns_true_at_boundary_word_count_600():
    assert is_suitable(reading_level=10.0, word_count=600, text="Normal text") is True


def test_is_suitable_returns_false_for_biblical_keyword():
    assert is_suitable(reading_level=10.0, word_count=200, text="This is a biblical reference") is False


def test_is_suitable_returns_false_for_sexually_keyword():
    assert is_suitable(reading_level=10.0, word_count=200, text="sexually explicit content") is False


def test_is_suitable_returns_false_for_pornographic_keyword():
    assert is_suitable(reading_level=10.0, word_count=200, text="pornographic material") is False


def test_is_suitable_returns_false_for_scripture_keyword():
    assert is_suitable(reading_level=10.0, word_count=200, text="scripture study") is False


def test_is_suitable_returns_false_for_erotica_keyword():
    assert is_suitable(reading_level=10.0, word_count=200, text="erotica novel") is False


def test_is_suitable_returns_false_for_holy_keyword():
    assert is_suitable(reading_level=10.0, word_count=200, text="holy scripture") is False


def test_is_suitable_returns_false_for_sacred_keyword():
    assert is_suitable(reading_level=10.0, word_count=200, text="sacred text") is False


# ── chunk_text ─────────────────────────────────────────────────────────────────


def test_chunk_text_returns_single_chunk_for_short_text():
    text = "word " * 100
    chunks = chunk_text(text, target_words=300)
    assert len(chunks) == 1


def test_chunk_text_splits_long_text_into_multiple_chunks():
    # 900 words, target 300 → expect ~3 chunks
    text = "This is a sentence. " * 200  # 800 words
    chunks = chunk_text(text, target_words=300)
    assert 2 <= len(chunks) <= 4


def test_chunk_text_returns_empty_list_for_empty_text():
    assert chunk_text("") == []


def test_chunk_text_preserves_all_words():
    words = ["word"] * 500
    text = " ".join(words)
    chunks = chunk_text(text, target_words=200)
    total = sum(len(c.split()) for c in chunks)
    assert total == 500


def test_chunk_text_chunks_respect_minimum_size():
    """Each chunk should be non-empty after stripping."""
    text = "A short sentence. " * 50
    chunks = chunk_text(text, target_words=200)
    for chunk in chunks:
        assert len(chunk.strip()) > 0


# ── process_raw_text ──────────────────────────────────────────────────────────


def test_process_raw_text_returns_passage_for_suitable_text():
    with patch("backend.app.scraper.processor.compute_reading_level", return_value=10.0):
        # Use text with enough "words" (>=50) to pass is_suitable
        text = "word " * 200
        passage = process_raw_text(text, source_url="https://example.com/1", source_title="Test")

    assert isinstance(passage, Passage)
    assert passage.source_url == "https://example.com/1"
    assert passage.source_title == "Test"
    assert passage.text == text
    assert passage.word_count == 200


def test_process_raw_text_passage_id_is_valid_uuid():
    with patch("backend.app.scraper.processor.compute_reading_level", return_value=10.0):
        text = "word " * 200
        passage = process_raw_text(text, source_url="https://example.com/1", source_title="Test")

    # Verify id is a valid UUID4 string
    parsed = uuid.UUID(passage.id)
    assert parsed.version == 4


def test_process_raw_text_embedding_is_none():
    with patch("backend.app.scraper.processor.compute_reading_level", return_value=10.0):
        text = "word " * 200
        passage = process_raw_text(text, source_url="https://example.com/1", source_title="Test")

    assert passage.embedding is None


def test_process_raw_text_figure_is_none():
    with patch("backend.app.scraper.processor.compute_reading_level", return_value=10.0):
        text = "word " * 200
        passage = process_raw_text(text, source_url="https://example.com/1", source_title="Test")

    assert passage.figure is None


def test_process_raw_text_raises_valueerror_for_unsuitable_text():
    with patch("backend.app.scraper.processor.compute_reading_level", return_value=5.0):
        # reading_level 5.0 < 8.0 → unsuitable
        text = "word " * 200
        with pytest.raises(ValueError, match="Passage not suitable"):
            process_raw_text(text, source_url="https://example.com/1", source_title="Test")


def test_process_raw_text_raises_valueerror_for_short_text():
    with patch("backend.app.scraper.processor.compute_reading_level", return_value=10.0):
        # word_count 20 < 50 → unsuitable
        text = "word " * 20
        with pytest.raises(ValueError, match="Passage not suitable"):
            process_raw_text(text, source_url="https://example.com/1", source_title="Test")


def test_process_raw_text_all_fields_populated():
    with patch("backend.app.scraper.processor.compute_reading_level", return_value=10.5):
        # 300 words → LONG type, essay-heavy → ESSAY category
        text = "essay discourse treatise subject " * 75  # 300 words
        passage = process_raw_text(text, source_url="https://example.com/2", source_title="Essay Title")

    assert passage.passage_type == PassageType.LONG   # 300 > 250
    assert passage.passage_category == PassageCategory.ESSAY  # essay keywords dominate
    assert passage.reading_level == 10.5
    assert passage.word_count == 300
