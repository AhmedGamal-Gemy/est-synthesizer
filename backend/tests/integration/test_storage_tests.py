"""Integration tests for backend.app.storage.tests — test_inventory CRUD."""

from datetime import datetime, timezone

import pytest

from backend.app.schemas import (
    AnswerChoice,
    DistractorRole,
    Difficulty,
    GeneratedModule,
    GeneratedPassageBlock,
    GeneratedQuestion,
    GeneratedTest,
    SkillType,
)


# ── factory helpers ──────────────────────────────────────────


def _make_answer_choices() -> list[AnswerChoice]:
    return [
        AnswerChoice(letter="A", text="Option A", distractor_role=DistractorRole.BEST_ANSWER),
        AnswerChoice(letter="B", text="Option B", distractor_role=DistractorRole.GOOD_NOT_BEST),
        AnswerChoice(letter="C", text="Option C", distractor_role=DistractorRole.COMPLETELY_WRONG),
        AnswerChoice(letter="D", text="Option D", distractor_role=DistractorRole.COMPLETELY_WRONG),
    ]


def _make_question(**overrides) -> GeneratedQuestion:
    defaults = {
        "id": "q-001",
        "passage_id": "p-001",
        "module_number": 1,
        "slot_number": 1,
        "question_number": 1,
        "question_text": "What is the answer?",
        "choices": _make_answer_choices(),
        "correct_answer": "A",
        "explanation": "A is correct",
        "supporting_line": "Line 1 says A",
        "skill_type": SkillType.INFORMATION_AND_IDEAS,
        "difficulty": Difficulty.MEDIUM,
    }
    defaults.update(overrides)
    return GeneratedQuestion(**defaults)


def _make_passage_block(**overrides) -> GeneratedPassageBlock:
    defaults = {
        "passage_id": "p-001",
        "passage_text": "Some passage text here.",
        "questions": [_make_question()],
    }
    defaults.update(overrides)
    return GeneratedPassageBlock(**defaults)


def _make_module(**overrides) -> GeneratedModule:
    defaults = {
        "module_number": 1,
        "module_type": "writing",
        "passages": [_make_passage_block()],
        "questions": [_make_question()],
        "question_count": 1,
    }
    defaults.update(overrides)
    return GeneratedModule(**defaults)


def _make_test(**overrides) -> GeneratedTest:
    defaults = {
        "id": "test-001",
        "job_id": "job-001",
        "blueprint_id": "default_blueprint_v1",
        "questions": [_make_question()],
        "modules": [_make_module()],
        "total_questions": 1,
        "created_at": datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        "student_pdf_path": None,
        "teacher_pdf_path": None,
    }
    defaults.update(overrides)
    return GeneratedTest(**defaults)


# ── monkeypatch fixture ──────────────────────────────────────


@pytest.fixture
async def db_conn_for_tests():
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


# ── CRUD tests ───────────────────────────────────────────────


class TestSaveAndGetTest:
    async def test_save_then_get_roundtrip(self, db_conn_for_tests):
        from backend.app.storage.tests import save_inventory_record, get_test

        test = _make_test()
        await save_inventory_record(test)

        fetched = await get_test(test.id)
        assert fetched is not None
        assert fetched["id"] == test.id
        assert fetched["job_id"] == test.job_id
        assert fetched["blueprint_id"] == test.blueprint_id
        assert fetched["total_questions"] == test.total_questions

    async def test_get_test_returns_none_for_nonexistent_id(self, db_conn_for_tests):
        from backend.app.storage.tests import get_test

        result = await get_test("nonexistent-id")
        assert result is None

    async def test_get_test_returns_dict_not_model(self, db_conn_for_tests):
        from backend.app.storage.tests import save_inventory_record, get_test

        test = _make_test()
        await save_inventory_record(test)

        fetched = await get_test(test.id)
        assert isinstance(fetched, dict)
        # It should NOT be a GeneratedTest instance
        assert not isinstance(fetched, GeneratedTest)


class TestListTests:
    async def test_list_tests_returns_all_ordered_by_created_at_desc(
        self, db_conn_for_tests
    ):
        from backend.app.storage.tests import save_inventory_record, list_tests

        # Insert 3 tests with staggered created_at timestamps
        t1 = _make_test(id="test-001", created_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        t2 = _make_test(id="test-002", created_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
        t3 = _make_test(id="test-003", created_at=datetime(2024, 3, 1, tzinfo=timezone.utc))

        await save_inventory_record(t1)
        await save_inventory_record(t2)
        await save_inventory_record(t3)

        results = await list_tests()
        assert len(results) == 3
        # Ordered by created_at DESC — most recent first
        assert results[0]["id"] == "test-002"  # June
        assert results[1]["id"] == "test-003"  # March
        assert results[2]["id"] == "test-001"  # January

    async def test_list_tests_with_limit_and_offset(self, db_conn_for_tests):
        from backend.app.storage.tests import save_inventory_record, list_tests

        t1 = _make_test(id="test-001", created_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        t2 = _make_test(id="test-002", created_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
        t3 = _make_test(id="test-003", created_at=datetime(2024, 3, 1, tzinfo=timezone.utc))

        await save_inventory_record(t1)
        await save_inventory_record(t2)
        await save_inventory_record(t3)

        # Get first 2 results
        results = await list_tests(limit=2, offset=0)
        assert len(results) == 2
        assert results[0]["id"] == "test-002"
        assert results[1]["id"] == "test-003"

        # Get remaining results
        results = await list_tests(limit=2, offset=2)
        assert len(results) == 1
        assert results[0]["id"] == "test-001"
