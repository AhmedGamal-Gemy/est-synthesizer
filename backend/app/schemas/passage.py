"""
EST Synthesizer - Passage Model
================================
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import PassageCategory, PassageType


class Passage(BaseModel):
    """A scraped or otherwise acquired source passage."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., description="UUID primary key")
    text: str = Field(..., description="Full passage text")
    source_url: str = Field(..., description="Origin URL of the passage")
    source_title: str = Field(..., description="Title of the source page/document")
    passage_type: PassageType = Field(..., description="LONG or SHORT")
    passage_category: PassageCategory = Field(
        ..., description="Content classification of the passage"
    )
    word_count: int = Field(..., ge=0, description="Number of words in text")
    reading_level: float = Field(
        ..., description="Flesch-Kincaid grade-level score"
    )
    embedding: Optional[List[float]] = Field(
        default=None, description="Vector embedding for Qdrant storage"
    )
    last_used_at: Optional[datetime] = Field(
        default=None, description="When this passage was last used in a test"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"Passage(id={self.id!r}, passage_type={self.passage_type.value!r}, "
            f"word_count={self.word_count})"
        )