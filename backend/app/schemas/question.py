"""
EST Synthesizer - Question Models
===================================
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import Difficulty, DistractorRole, SkillType


class AnswerChoice(BaseModel):
    """A single answer choice within a multiple-choice question."""

    model_config = ConfigDict(strict=True)

    letter: str = Field(
        ..., pattern="^[A-D]$", description="Answer choice letter"
    )
    text: str = Field(..., description="Answer choice text")
    distractor_role: DistractorRole = Field(
        ..., description="Pedagogical role of this choice"
    )


class GeneratedQuestion(BaseModel):
    """A single question produced by the generation pipeline."""

    model_config = ConfigDict(strict=True)

    id: str = Field(..., description="UUID primary key")
    passage_id: str = Field(..., description="FK to the source Passage")
    module_number: int = Field(
        ..., ge=1, le=3, description="EST module (1, 2, or 3)"
    )
    slot_number: int = Field(..., ge=1, description="Slot within the module")
    question_number: int = Field(
        ..., ge=1, description="Sequential number across the full test"
    )
    question_text: str = Field(..., description="The question prompt")
    choices: List[AnswerChoice] = Field(
        ..., min_length=4, max_length=4, description="Four answer choices (A-D)"
    )
    correct_answer: str = Field(
        ..., description="Correct choice letter (A, B, C, or D)"
    )
    explanation: str = Field(..., description="Why the correct answer is right")
    supporting_line: str = Field(
        ..., description="Substring of the passage that supports the answer"
    )
    skill_type: SkillType = Field(..., description="Skill being assessed")
    difficulty: Difficulty = Field(..., description="Relative difficulty")
    scope_mismatch: Optional[bool] = Field(
        default=None, description="Reserved for future use (MVP: always None)"
    )
    is_cumulative: Optional[bool] = Field(
        default=None, description="Reserved for future use (MVP: always None)"
    )
    editing_targets: Optional[List[str]] = Field(
        default=None, description="Reserved for future use (MVP: always None)"
    )

    @field_validator("choices")
    @classmethod
    def validate_distractor_roles(cls, choices: List[AnswerChoice]) -> List[AnswerChoice]:
        """Ensure exactly one BEST_ANSWER, one GOOD_NOT_BEST, two COMPLETELY_WRONG."""
        roles = [c.distractor_role for c in choices]
        if roles.count(DistractorRole.BEST_ANSWER) != 1:
            raise ValueError(
                f"Expected exactly 1 BEST_ANSWER, got {roles.count(DistractorRole.BEST_ANSWER)}"
            )
        if roles.count(DistractorRole.GOOD_NOT_BEST) != 1:
            raise ValueError(
                f"Expected exactly 1 GOOD_NOT_BEST, got {roles.count(DistractorRole.GOOD_NOT_BEST)}"
            )
        if roles.count(DistractorRole.COMPLETELY_WRONG) != 2:
            raise ValueError(
                f"Expected exactly 2 COMPLETELY_WRONG, got {roles.count(DistractorRole.COMPLETELY_WRONG)}"
            )
        return choices

    def __repr__(self) -> str:
        return (
            f"GeneratedQuestion(id={self.id!r}, module={self.module_number}, "
            f"slot={self.slot_number}, difficulty={self.difficulty.value!r})"
        )


class GeneratedPassageBlock(BaseModel):
    """A passage paired with the questions that reference it."""

    model_config = ConfigDict(strict=True)

    passage_id: str = Field(..., description="FK to Passage")
    passage_text: str = Field(..., description="Full text of the passage")
    questions: List[GeneratedQuestion] = Field(
        ..., description="Questions tied to this passage"
    )

    def __repr__(self) -> str:
        return (
            f"GeneratedPassageBlock(passage_id={self.passage_id!r}, "
            f"questions={len(self.questions)})"
        )