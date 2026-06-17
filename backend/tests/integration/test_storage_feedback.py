"""Integration tests for backend.app.storage.feedback — QuestionFeedback CRUD."""

import json
from datetime import datetime, timezone

import pytest

from backend.app.schemas import QuestionFeedback, QuestionFlag


# ── helpers ──────────────────────────────────────────────────


def _make_feedback(**overrides) -> QuestionFeedback:
    defaults = {
        "id": "fb-001",
        "test_id": "test-001",
        "question_id": "q-001",
        "rating": 3,
        "flags": [QuestionFlag.AMBIGUOUS],
        "notes": "Looks okay",
        "created_at": datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return QuestionFeedback(**defaults)


# ── monkeypatch fixture ──────────────────────────────────────


@pytest.fixture
async def db_conn_for_feedback():
    """In-memory SQLite with schema + monkeypatched db module."""
    import aiosqlite
    import backend.app.storage.db as db_mod

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(db_mod.SCHEMA_SQL)
    await conn.commit()

    original_conn = db_mod._conn
    original_path = db_mod.DB_PATH
    db_mod._conn = conn
    db_mod.DB_PATH = ":memory:"
    yield conn
    db_mod._conn = original_conn
    db_mod.DB_PATH = original_path
    await conn.close()


# ── pure function tests ──────────────────────────────────────


class TestSerializeFlags:
    def test_serialize_flags_converts_list_to_json_string(self):
        from backend.app.storage.feedback import _serialize_flags

        flags = [QuestionFlag.AMBIGUOUS, QuestionFlag.TOO_EASY]
        result = _serialize_flags(flags)
        # Enum auto() values are string integers for (str, Enum)
        parsed = json.loads(result)
        assert parsed == [QuestionFlag.AMBIGUOUS.value, QuestionFlag.TOO_EASY.value]

    def test_serialize_flags_empty_list(self):
        from backend.app.storage.feedback import _serialize_flags

        result = _serialize_flags([])
        parsed = json.loads(result)
        assert parsed == []


class TestDeserializeFlags:
    def test_deserialize_flags_converts_json_string_to_list(self):
        from backend.app.storage.feedback import _deserialize_flags

        # auto() values are string integers: AMBIGUOUS="1", TOO_EASY="4"
        result = _deserialize_flags(json.dumps([QuestionFlag.AMBIGUOUS.value, QuestionFlag.TOO_EASY.value]))
        assert result == [QuestionFlag.AMBIGUOUS, QuestionFlag.TOO_EASY]

    def test_deserialize_flags_roundtrip(self):
        from backend.app.storage.feedback import _serialize_flags, _deserialize_flags

        original = [QuestionFlag.AMBIGUOUS, QuestionFlag.TOO_HARD, QuestionFlag.INCORRECT_ANSWER]
        serialized = _serialize_flags(original)
        deserialized = _deserialize_flags(serialized)
        assert deserialized == original

    def test_deserialize_flags_single_flag(self):
        from backend.app.storage.feedback import _deserialize_flags

        # POORLY_PHRASED auto() value is "2"
        result = _deserialize_flags(json.dumps([QuestionFlag.POORLY_PHRASED.value]))
        assert result == [QuestionFlag.POORLY_PHRASED]


# ── CRUD tests ───────────────────────────────────────────────


class TestSaveAndGetFeedback:
    async def test_save_then_get_roundtrip(self, db_conn_for_feedback):
        from backend.app.storage.feedback import save_feedback, get_feedback_by_test

        fb = _make_feedback()
        await save_feedback(fb)

        results = await get_feedback_by_test(fb.test_id)
        assert len(results) == 1
        fetched = results[0]
        assert fetched.id == fb.id
        assert fetched.test_id == fb.test_id
        assert fetched.question_id == fb.question_id
        assert fetched.rating == fb.rating
        assert fetched.flags == fb.flags
        assert fetched.notes == fb.notes

    async def test_save_feedback_rejects_rating_outside_range(self):
        """Test save_feedback's explicit ValueError for ratings outside 1-5.
        Pydantic already validates this, so we bypass it with model_construct."""
        from backend.app.storage.feedback import save_feedback

        fb = QuestionFeedback.model_construct(
            id="fb-bad", test_id="test-001", question_id="q-001",
            rating=6, flags=[QuestionFlag.AMBIGUOUS], notes="bad",
            created_at=datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            await save_feedback(fb)

    async def test_save_feedback_rejects_rating_zero(self):
        """Test save_feedback's explicit ValueError for rating=0.
        Pydantic already validates this, so we bypass it with model_construct."""
        from backend.app.storage.feedback import save_feedback

        fb = QuestionFeedback.model_construct(
            id="fb-zero", test_id="test-001", question_id="q-001",
            rating=0, flags=[QuestionFlag.AMBIGUOUS], notes="bad",
            created_at=datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            await save_feedback(fb)

    async def test_get_feedback_by_test_returns_empty_for_nonexistent_test(
        self, db_conn_for_feedback
    ):
        from backend.app.storage.feedback import get_feedback_by_test

        results = await get_feedback_by_test("nonexistent-test-id")
        assert results == []

    async def test_multiple_feedback_entries_for_same_test(self, db_conn_for_feedback):
        from backend.app.storage.feedback import save_feedback, get_feedback_by_test

        fb1 = _make_feedback(id="fb-001", question_id="q-001")
        fb2 = _make_feedback(id="fb-002", question_id="q-002", rating=5)
        await save_feedback(fb1)
        await save_feedback(fb2)

        results = await get_feedback_by_test("test-001")
        assert len(results) == 2
