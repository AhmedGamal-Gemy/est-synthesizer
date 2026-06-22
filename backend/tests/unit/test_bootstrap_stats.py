"""Unit tests for scripts.bootstrap.stats — StatsTracker."""

from scripts.bootstrap.stats import StatsTracker
from backend.app.schemas import Passage, PassageCategory, PassageType


def _passage(
    passage_type: PassageType = PassageType.LONG,
    passage_category: PassageCategory = PassageCategory.SCIENTIFIC,
    reading_level: float = 9.5,
    word_count: int = 300,
) -> Passage:
    return Passage(
        id="p-test",
        text="word " * word_count,
        source_url="https://example.com/test",
        source_title="Test",
        passage_type=passage_type,
        passage_category=passage_category,
        word_count=word_count,
        reading_level=reading_level,
    )


# ── Init ──────────────────────────────────────────────────────────────────────


def test_stats_tracker_init():
    stats = StatsTracker()
    assert stats.total_books == 0
    assert stats.total_passages == 0
    assert stats.passages_by_type == {}
    assert stats.passages_by_category == {}
    assert stats.reading_levels == []
    assert stats.errors == 0


# ── record_passage ────────────────────────────────────────────────────────────


def test_record_passage_increments_total():
    stats = StatsTracker()
    stats.record_passage(_passage())
    assert stats.total_passages == 1


def test_record_passage_tracks_type():
    stats = StatsTracker()
    stats.record_passage(_passage(passage_type=PassageType.LONG))
    stats.record_passage(_passage(passage_type=PassageType.SHORT))
    assert stats.passages_by_type == {"long": 1, "short": 1}


def test_record_passage_tracks_category():
    stats = StatsTracker()
    stats.record_passage(_passage(passage_category=PassageCategory.SCIENTIFIC))
    stats.record_passage(_passage(passage_category=PassageCategory.HISTORY))
    assert stats.passages_by_category == {"scientific": 1, "history": 1}


def test_record_passage_appends_reading_level():
    stats = StatsTracker()
    stats.record_passage(_passage(reading_level=8.0))
    stats.record_passage(_passage(reading_level=12.0))
    assert stats.reading_levels == [8.0, 12.0]


def test_record_passage_accumulates_same_type():
    stats = StatsTracker()
    stats.record_passage(_passage(passage_type=PassageType.LONG))
    stats.record_passage(_passage(passage_type=PassageType.LONG))
    assert stats.passages_by_type["long"] == 2


def test_record_passage_accumulates_same_category():
    stats = StatsTracker()
    stats.record_passage(_passage(passage_category=PassageCategory.SCIENTIFIC))
    stats.record_passage(_passage(passage_category=PassageCategory.SCIENTIFIC))
    assert stats.passages_by_category["scientific"] == 2


# ── record_error ──────────────────────────────────────────────────────────────


def test_record_error_increments():
    stats = StatsTracker()
    stats.record_error()
    assert stats.errors == 1


def test_record_error_accumulates():
    stats = StatsTracker()
    stats.record_error()
    stats.record_error()
    stats.record_error()
    assert stats.errors == 3


# ── report ────────────────────────────────────────────────────────────────────


def test_report_includes_total_books():
    stats = StatsTracker()
    stats.total_books = 42
    report = stats.report()
    assert "42" in report


def test_report_includes_total_passages():
    stats = StatsTracker()
    stats.record_passage(_passage())
    report = stats.report()
    assert "1" in report


def test_report_includes_error_count():
    stats = StatsTracker()
    stats.record_error()
    report = stats.report()
    assert "1" in report


def test_report_includes_average_reading_level():
    stats = StatsTracker()
    stats.record_passage(_passage(reading_level=10.0))
    stats.record_passage(_passage(reading_level=12.0))
    report = stats.report()
    assert "11.0" in report  # (10+12)/2


def test_report_shows_zero_reading_level_when_no_passages():
    stats = StatsTracker()
    report = stats.report()
    assert "0.0" in report


def test_report_includes_breakdown_by_type():
    stats = StatsTracker()
    stats.record_passage(_passage(passage_type=PassageType.LONG))
    report = stats.report()
    assert "long" in report


def test_report_includes_breakdown_by_category_top_5():
    stats = StatsTracker()
    stats.record_passage(_passage(passage_category=PassageCategory.SCIENTIFIC))
    report = stats.report()
    assert "scientific" in report


def test_report_returns_string():
    stats = StatsTracker()
    assert isinstance(stats.report(), str)
