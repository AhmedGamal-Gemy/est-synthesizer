"""
EST Synthesizer - Generation Job Model
========================================
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import JobStatus


class GenerationJob(BaseModel):
    """Tracks the async lifecycle of a test generation request."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., description="UUID primary key")
    status: JobStatus = Field(..., description="Current job status")
    blueprint_id: str = Field(..., description="FK to TestBlueprint")
    total_slots: int = Field(
        ..., ge=0, description="Total question slots to fill"
    )
    completed_slots: int = Field(
        ..., ge=0, description="Slots successfully filled"
    )
    failed_slots: int = Field(
        ..., ge=0, description="Slots that failed generation"
    )
    result_test_id: Optional[str] = Field(
        default=None, description="FK to GeneratedTest once complete"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error details if status is FAILED"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp (UTC)",
    )

    @property
    def progress(self) -> int:
        """Completion percentage (0-100), auto-calculated from slot counts."""
        if self.total_slots == 0:
            return 0
        return int((self.completed_slots / self.total_slots) * 100)

    def __repr__(self) -> str:
        return (
            f"GenerationJob(id={self.id!r}, status={self.status.value!r}, "
            f"progress={self.progress}%)"
        )