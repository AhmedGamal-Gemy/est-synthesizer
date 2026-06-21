"""EST Synthesizer - Question Feedback CRUD."""

from __future__ import annotations

import json
import structlog
from datetime import datetime
from typing import List

from backend.app.schemas import QuestionFeedback, QuestionFlag
from backend.app.storage.db import _ensure_utc, get_connection

logger = structlog.get_logger(__name__)

INSERT_FEEDBACK_SQL = """
INSERT INTO question_feedback
    (id, test_id, question_id, rating, flags, notes, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""
SELECT_FEEDBACK_BY_TEST_SQL = """
SELECT * FROM question_feedback
WHERE test_id = ?
ORDER BY created_at DESC
"""


def _serialize_flags(flags: List[QuestionFlag]) -> str:
    return json.dumps([f.value for f in flags])


def _deserialize_flags(raw: str) -> List[QuestionFlag]:
    return [QuestionFlag(v) for v in json.loads(raw)]


async def save_feedback(feedback: QuestionFeedback) -> None:
    if not (1 <= feedback.rating <= 5):
        raise ValueError("Rating must be between 1 and 5")
    try:
        async with get_connection() as db:
            await db.execute(INSERT_FEEDBACK_SQL, (
                feedback.id, feedback.test_id, feedback.question_id,
                feedback.rating, _serialize_flags(feedback.flags),
                feedback.notes,
                _ensure_utc(feedback.created_at).isoformat(),
            ))
            await db.commit()
        logger.debug("Feedback saved", feedback_id=feedback.id)
    except ValueError:
        raise
    except Exception:
        logger.exception("Failed to save feedback", feedback_id=feedback.id)
        raise


async def get_feedback_by_test(test_id: str) -> list[QuestionFeedback]:
    try:
        async with get_connection() as db:
            async with db.execute(
                SELECT_FEEDBACK_BY_TEST_SQL, (test_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            QuestionFeedback(
                id=r["id"], test_id=r["test_id"],
                question_id=r["question_id"], rating=r["rating"],
                flags=_deserialize_flags(r["flags"]),
                notes=r["notes"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]
    except Exception:
        logger.exception("Failed to fetch feedback for test", test_id=test_id)
        raise
