"""Integration tests for backend.app.storage.qdrant — _build_filter pure function."""

from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    Range,
)


class TestBuildFilter:
    """Tests for _build_filter — no Qdrant server needed."""

    def test_exact_match_filter(self):
        from backend.app.storage.qdrant import _build_filter

        result = _build_filter({"passage_type": "long"})
        assert isinstance(result, Filter)
        assert len(result.must) == 1
        cond = result.must[0]
        assert isinstance(cond, FieldCondition)
        assert cond.key == "passage_type"
        assert isinstance(cond.match, MatchValue)
        assert cond.match.value == "long"

    def test_range_filter(self):
        from backend.app.storage.qdrant import _build_filter

        result = _build_filter({"reading_level": {"gte": 8, "lte": 14}})
        assert isinstance(result, Filter)
        assert len(result.must) == 1
        cond = result.must[0]
        assert isinstance(cond, FieldCondition)
        assert cond.key == "reading_level"
        assert isinstance(cond.range, Range)
        assert cond.range.gte == 8
        assert cond.range.lte == 14

    def test_mixed_filter_exact_and_range(self):
        from backend.app.storage.qdrant import _build_filter

        result = _build_filter({
            "passage_type": "long",
            "reading_level": {"gte": 8, "lte": 14},
        })
        assert isinstance(result, Filter)
        assert len(result.must) == 2

        # Find the exact match condition
        exact = [c for c in result.must if isinstance(c.match, MatchValue)]
        range_conds = [c for c in result.must if isinstance(c.range, Range)]

        assert len(exact) == 1
        assert exact[0].key == "passage_type"
        assert exact[0].match.value == "long"

        assert len(range_conds) == 1
        assert range_conds[0].key == "reading_level"
        assert range_conds[0].range.gte == 8
        assert range_conds[0].range.lte == 14

    def test_empty_dict_produces_filter_with_empty_must(self):
        from backend.app.storage.qdrant import _build_filter

        result = _build_filter({})
        assert isinstance(result, Filter)
        assert len(result.must) == 0

    def test_range_filter_with_only_gte(self):
        from backend.app.storage.qdrant import _build_filter

        result = _build_filter({"word_count": {"gte": 100}})
        cond = result.must[0]
        assert isinstance(cond.range, Range)
        assert cond.range.gte == 100
        assert cond.range.lte is None

    def test_multiple_exact_match_conditions(self):
        from backend.app.storage.qdrant import _build_filter

        result = _build_filter({
            "passage_type": "short",
            "passage_category": "essay",
        })
        assert len(result.must) == 2
        keys = [c.key for c in result.must]
        assert "passage_type" in keys
        assert "passage_category" in keys
