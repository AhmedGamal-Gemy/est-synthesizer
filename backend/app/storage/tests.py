"""EST Synthesizer - Test Inventory CRUD."""

from __future__ import annotations

import structlog

from backend.app.schemas import GeneratedTest
from backend.app.storage.db import _ensure_utc, get_connection

logger = structlog.get_logger(__name__)

INSERT_TEST_SQL = """
INSERT INTO test_inventory
    (id, job_id, blueprint_id, total_questions,
     student_pdf_path, teacher_pdf_path, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""
SELECT_TEST_SQL = "SELECT * FROM test_inventory WHERE id = ?"
LIST_TESTS_SQL = """
SELECT * FROM test_inventory
ORDER BY created_at DESC
LIMIT ? OFFSET ?
"""


async def save_inventory_record(test: GeneratedTest) -> None:
    try:
        async with get_connection() as db:
            await db.execute(INSERT_TEST_SQL, (
                test.id, test.job_id, test.blueprint_id,
                test.total_questions, test.student_pdf_path,
                test.teacher_pdf_path,
                _ensure_utc(test.created_at).isoformat(),
            ))
            await db.commit()
        logger.debug("Test saved", test_id=test.id)
    except Exception:
        logger.exception("Failed to save test", test_id=test.id)
        raise


async def get_test(test_id: str) -> dict | None:
    try:
        async with get_connection() as db:
            async with db.execute(SELECT_TEST_SQL, (test_id,)) as cursor:
                row = await cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("Failed to fetch test", test_id=test_id)
        raise


async def list_tests(limit: int = 20, offset: int = 0) -> list[dict]:
    try:
        async with get_connection() as db:
            async with db.execute(LIST_TESTS_SQL, (limit, offset)) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("Failed to list tests", limit=limit, offset=offset)
        raise
