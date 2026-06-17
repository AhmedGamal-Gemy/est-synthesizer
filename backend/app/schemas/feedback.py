"""
EST Synthesizer - Feedback Model
==================================
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import QuestionFlag


class QuestionFeedback(BaseModel):
    """Human review feedback attached to a specific question in a test."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., description="UUID primary key")
    test_id: str = Field(..., description="FK to GeneratedTest")
    question_id: str = Field(..., description="FK to GeneratedQuestion")
    rating: int = Field(
        ..., ge=1, le=5, description="Quality rating (1-5 stars)"
    )
    flags: List[QuestionFlag] = Field(
        ..., description="Flags raised by the reviewer"
    )
    notes: Optional[str] = Field(
        default=None, description="Free-form reviewer notes"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"QuestionFeedback(id={self.id!r}, test_id={self.test_id!r}, "
            f"rating={self.rating})"
        )