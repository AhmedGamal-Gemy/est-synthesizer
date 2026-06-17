"""Unit tests for Qdrant _build_filter (pure function, no server needed)."""

from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from backend.app.storage.qdrant import _build_filter


class TestBuildFilterExactMatch:
    """Exact-match filters produce FieldCondition with MatchValue."""

    def test_single_exact_match(self):
        result = _build_filter({"passage_type": "long"})
        assert isinstance(result, Filter)
        assert len(result.must) == 1
        cond = result.must[0]
        assert isinstance(cond, FieldCondition)
        assert cond.key == "passage_type"
        assert isinstance(cond.match, MatchValue)
        assert cond.match.value == "long"

    def test_multiple_exact_matches(self):
        result = _build_filter({"passage_type": "short", "passage_category": "essay"})
        assert len(result.must) == 2
        keys = [c.key for c in result.must]
        assert "passage_type" in keys
        assert "passage_category" in keys


class TestBuildFilterRange:
    """Range filters produce FieldCondition with Range."""

    def test_range_with_gte_and_lte(self):
        result = _build_filter({"reading_level": {"gte": 8, "lte": 14}})
        assert len(result.must) == 1
        cond = result.must[0]
        assert isinstance(cond, FieldCondition)
        assert cond.key == "reading_level"
        assert isinstance(cond.range, Range)
        assert cond.range.gte == 8
        assert cond.range.lte == 14

    def test_range_with_only_gte(self):
        result = _build_filter({"word_count": {"gte": 100}})
        cond = result.must[0]
        assert isinstance(cond.range, Range)
        assert cond.range.gte == 100
        assert cond.range.lte is None

    def test_range_with_only_lte(self):
        result = _build_filter({"word_count": {"lte": 500}})
        cond = result.must[0]
        assert cond.range.gte is None
        assert cond.range.lte == 500


class TestBuildFilterMixed:
    """Mixed exact-match and range conditions."""

    def test_mixed_filter(self):
        result = _build_filter({
            "passage_type": "long",
            "reading_level": {"gte": 8, "lte": 14},
        })
        assert len(result.must) == 2
        exact_cond = [c for c in result.must if isinstance(c.match, MatchValue)]
        range_cond = [c for c in result.must if isinstance(c.range, Range)]
        assert len(exact_cond) == 1
        assert len(range_cond) == 1


class TestBuildFilterEmpty:
    """Empty dict produces Filter with empty must list."""

    def test_empty_dict(self):
        result = _build_filter({})
        assert isinstance(result, Filter)
        assert result.must == []
