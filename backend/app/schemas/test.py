"""
EST Synthesizer - Test & Blueprint Models
===========================================
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import Difficulty, ModuleType, SkillType
from .question import GeneratedPassageBlock, GeneratedQuestion


class GeneratedModule(BaseModel):
    """One module within a generated test."""

    model_config = ConfigDict(strict=True)

    module_number: int = Field(
        ..., ge=1, le=3, description="Module index (1-3)"
    )
    module_type: ModuleType = Field(
        ...,
        description="One of: writing, reading_long, reading_short",
    )
    passages: List[GeneratedPassageBlock] = Field(
        ..., description="Passages in this module"
    )
    questions: List[GeneratedQuestion] = Field(
        ..., description="All questions in this module"
    )
    question_count: int = Field(..., ge=0, description="Total question count")

    def __repr__(self) -> str:
        return (
            f"GeneratedModule(module_number={self.module_number}, "
            f"module_type={self.module_type.value!r}, questions={self.question_count})"
        )


class GeneratedTest(BaseModel):
    """A fully assembled test ready for PDF export."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., description="UUID primary key")
    job_id: str = Field(..., description="FK to the GenerationJob that created it")
    blueprint_id: str = Field(..., description="FK to the TestBlueprint used")
    questions: List[GeneratedQuestion] = Field(
        ..., description="Flat list of all questions"
    )
    modules: List[GeneratedModule] = Field(
        ..., description="Organized by module"
    )
    total_questions: int = Field(..., ge=0, description="Total question count")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp (UTC)",
    )
    student_pdf_path: Optional[str] = Field(
        default=None, description="Filesystem path to the student-facing PDF"
    )
    teacher_pdf_path: Optional[str] = Field(
        default=None, description="Filesystem path to the teacher-facing PDF"
    )

    def __repr__(self) -> str:
        return (
            f"GeneratedTest(id={self.id!r}, total_questions={self.total_questions}, "
            f"modules={len(self.modules)})"
        )


class ModuleSlot(BaseModel):
    """A single question slot within a module blueprint."""

    model_config = ConfigDict(strict=True)

    slot_number: int = Field(..., ge=1, description="Slot index within the module")
    skill_type: SkillType = Field(..., description="Skill being assessed")
    difficulty: Difficulty = Field(..., description="Relative difficulty")
    question_count: int = Field(
        ..., ge=1, description="Number of questions for this slot"
    )
    has_figure: bool = Field(
        default=False, description="Whether this slot requires a figure"
    )
    easy_count: int = Field(default=0, ge=0, description="Number of easy questions in this slot")
    medium_count: int = Field(default=0, ge=0, description="Number of medium questions in this slot")
    hard_count: int = Field(default=0, ge=0, description="Number of hard questions in this slot")

    @model_validator(mode="after")
    def _validate_difficulty_counts(self) -> "ModuleSlot":
        if self.easy_count + self.medium_count + self.hard_count != self.question_count:
            raise ValueError(
                "easy_count + medium_count + hard_count must equal question_count"
            )
        return self


class ModuleConfig(BaseModel):
    """Configuration for a single module within a test blueprint."""

    model_config = ConfigDict(strict=True)

    module_number: int = Field(
        ..., ge=1, le=3, description="Module index (1-3)"
    )
    module_type: ModuleType = Field(
        ...,
        description="One of: writing, reading_long, or reading_short",
    )
    slots: List[ModuleSlot] = Field(
        ..., min_length=1, description="Question slots for this module"
    )
    has_figure: bool = Field(
        default=False, description="Whether this module contains a figure"
    )
    wordy_answer_style: bool = Field(
        default=False,
        description="True for Module 1 (writing) which uses longer answer choices",
    )

    @property
    def question_count(self) -> int:
        """Total number of questions across all slots in this module."""
        return sum(slot.question_count for slot in self.slots)


class TestBlueprint(BaseModel):
    """Template that defines the structure of a test."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., description="UUID primary key")
    name: str = Field(
        ...,
        examples=["DEFAULT_BLUEPRINT"],
        description="Human-readable blueprint name",
    )
    modules: List[ModuleConfig] = Field(
        ..., min_length=1, description="Module configurations for this blueprint"
    )
    total_questions: int = Field(
        ..., ge=0, description="Total questions across all modules"
    )
    difficulty_distribution: dict = Field(
        ...,
        description="Fraction per difficulty: {easy: float, medium: float, hard: float}",
    )

    def __repr__(self) -> str:
        return (
            f"TestBlueprint(id={self.id!r}, name={self.name!r}, "
            f"total_questions={self.total_questions})"
        )