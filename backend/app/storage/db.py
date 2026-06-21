"""EST Synthesizer - Database connection & schema initialisation."""

from __future__ import annotations

import structlog
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import AsyncGenerator

import aiosqlite

# BLUEPRINT_TABLE_SQL is inlined below to avoid circular imports

logger = structlog.get_logger(__name__)

DB_PATH: str = "data/db/est.db"
_conn: aiosqlite.Connection | None = None
_lock: Lock = Lock()


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@asynccontextmanager
async def get_connection() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Shared async connection (opened once, reused)."""
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                _conn = await aiosqlite.connect(DB_PATH)
                _conn.row_factory = aiosqlite.Row
                await _conn.execute("PRAGMA journal_mode=WAL")
                await _conn.execute("PRAGMA foreign_keys=ON")
                logger.info("SQLite connection opened", db_path=str(DB_PATH))
    try:
        yield _conn
    except Exception:
        logger.exception("SQLite connection error")
        raise


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS generation_jobs (
    id               TEXT PRIMARY KEY,
    status           TEXT NOT NULL,
    blueprint_id     TEXT NOT NULL,
    total_slots      INTEGER NOT NULL,
    completed_slots  INTEGER NOT NULL,
    failed_slots     INTEGER NOT NULL,
    result_test_id   TEXT,
    error_message    TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS test_inventory (
    id               TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL,
    blueprint_id     TEXT NOT NULL,
    total_questions  INTEGER NOT NULL,
    student_pdf_path TEXT,
    teacher_pdf_path TEXT,
    created_at       TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES generation_jobs(id)
);
CREATE TABLE IF NOT EXISTS question_feedback (
    id          TEXT PRIMARY KEY,
    test_id     TEXT NOT NULL,
    question_id TEXT NOT NULL,
    rating      INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
    flags       TEXT NOT NULL,
    notes       TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (test_id) REFERENCES test_inventory(id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_status       ON generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created      ON generation_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_inventory_created ON test_inventory(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_test     ON question_feedback(test_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON question_feedback(created_at);
CREATE TABLE IF NOT EXISTS blueprints (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    blueprint_json  TEXT NOT NULL,
    is_builtin      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
"""


async def init_db() -> None:
    """Create tables + indexes if they don't exist."""
    try:
        async with get_connection() as db:
            await db.executescript(SCHEMA_SQL)
            await db.commit()
        # lazy import avoids circular dep (blueprints → db → blueprints)
        from backend.app.storage.blueprints import seed_builtin_blueprints  # fmt: skip
        await seed_builtin_blueprints()
        logger.info("Database schema initialised.")
    except Exception:
        logger.exception("Failed to initialise database schema")
        raise
