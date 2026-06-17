"""Integration tests for backend.app.storage.db — schema, UTC helper, seeding."""

from datetime import datetime, timezone

import pytest
import aiosqlite

from backend.app.storage.db import SCHEMA_SQL, _ensure_utc, init_db


# ── _ensure_utc ──────────────────────────────────────────────


class TestEnsureUtc:
    def test_naive_datetime_gets_utc(self):
        naive = datetime(2024, 6, 15, 12, 30, 0)
        result = _ensure_utc(naive)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc
        assert result.year == 2024
        assert result.hour == 12

    def test_utc_datetime_stays_unchanged(self):
        aware = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        result = _ensure_utc(aware)
        assert result.tzinfo == timezone.utc
        assert result == aware

    def test_non_utc_timezone_stays_unchanged(self):
        """_ensure_utc does NOT convert other tz — it just ensures tzinfo is set."""
        from datetime import timedelta
        # Eastern timezone offset UTC-5
        tz_minus5 = timezone(timedelta(hours=-5))
        aware = datetime(2024, 6, 15, 12, 30, 0, tzinfo=tz_minus5)
        result = _ensure_utc(aware)
        assert result.tzinfo is tz_minus5  # stays as-is, not converted


# ── In-memory SQLite fixture tests ───────────────────────────


class TestDbConnFixture:
    @pytest.fixture
    async def db_conn(self):
        conn = await aiosqlite.connect(":memory:")
        conn.row_factory = aiosqlite.Row
        await conn.executescript(SCHEMA_SQL)
        await conn.commit()
        yield conn
        await conn.close()

    async def test_all_four_tables_exist(self, db_conn):
        cursor = await db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        table_names = [r["name"] for r in rows]
        assert "generation_jobs" in table_names
        assert "test_inventory" in table_names
        assert "question_feedback" in table_names
        assert "blueprints" in table_names

    async def test_indexes_exist(self, db_conn):
        cursor = await db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        rows = await cursor.fetchall()
        index_names = [r["name"] for r in rows]
        expected_indexes = [
            "idx_jobs_status",
            "idx_jobs_created",
            "idx_inventory_created",
            "idx_feedback_test",
            "idx_feedback_created",
        ]
        for idx in expected_indexes:
            assert idx in index_names, f"Missing index: {idx}"


# ── init_db with seeding ─────────────────────────────────────


class TestInitDbSeeding:
    @pytest.fixture
    async def seeded_db(self):
        """In-memory DB with init_db + seeding, using monkeypatch."""
        import backend.app.storage.db as db_mod

        conn = await aiosqlite.connect(":memory:")
        conn.row_factory = aiosqlite.Row
        await conn.executescript(SCHEMA_SQL)
        await conn.commit()

        original_conn = db_mod._conn
        original_path = db_mod.DB_PATH
        db_mod._conn = conn
        db_mod.DB_PATH = ":memory:"
        try:
            await init_db()
            yield conn
        finally:
            db_mod._conn = original_conn
            db_mod.DB_PATH = original_path
            await conn.close()

    async def test_blueprints_table_has_two_rows_after_seeding(self, seeded_db):
        cursor = await seeded_db.execute("SELECT COUNT(*) AS cnt FROM blueprints")
        row = await cursor.fetchone()
        assert row["cnt"] == 2
