"""
EST Synthesizer — Question Feedback API Endpoints (T18)

POST /api/tests/{test_id}/questions/{question_id}/feedback
    Submit a review rating (1-5) with optional flags and notes for a question.

GET /api/tests/{test_id}/feedback
    Retrieve all feedback records for a given test.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.schemas import QuestionFlag
from backend.app.schemas.feedback import QuestionFeedback
from backend.app.storage.feedback import get_feedback_by_test, save_feedback

router = APIRouter(prefix="/api/tests", tags=["feedback"])
log = structlog.get_logger(__name__)


# ── request / response models ──────────────────────────────


class PostFeedbackIn(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Quality rating 1-5")
    flags: list[QuestionFlag] = Field(
        default_factory=list, description="Flags raised by the reviewer"
    )
    notes: str | None = Field(default=None, description="Free-form reviewer notes")


class PostFeedbackOut(BaseModel):
    success: bool
    feedback_id: str


class FeedbackOut(BaseModel):
    id: str
    test_id: str
    question_id: str
    rating: int
    flags: list[str]
    notes: str | None
    created_at: str


# ── endpoints ───────────────────────────────────────────────


@router.post("/{test_id}/questions/{question_id}/feedback", status_code=201)
async def post_feedback(test_id: str, question_id: str, body: PostFeedbackIn):
    """Submit feedback for a specific question in a test.

    Returns the created feedback_id on success.
    """
    feedback = QuestionFeedback(
        id=uuid.uuid4().hex[:12],
        test_id=test_id,
        question_id=question_id,
        rating=body.rating,
        flags=body.flags,
        notes=body.notes,
    )
    try:
        await save_feedback(feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    log.info("Feedback submitted", feedback_id=feedback.id, test_id=test_id, question_id=question_id)
    return PostFeedbackOut(success=True, feedback_id=feedback.id)


@router.get("/{test_id}/feedback")
async def list_feedback(test_id: str):
    """Retrieve all feedback records for a test, newest first."""
    records = await get_feedback_by_test(test_id)
    return [
        FeedbackOut(
            id=r.id,
            test_id=r.test_id,
            question_id=r.question_id,
            rating=r.rating,
            flags=[f.value for f in r.flags],
            notes=r.notes,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]
