"""
EST Synthesizer - Question Models
===================================
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import Difficulty, DistractorRole, SkillType

# Fallback mapping for LLM-invented skill types that don't match our enum
_SKILL_FALLBACK_MAP: dict[str, SkillType] = {
    "inference": SkillType.INFORMATION_AND_IDEAS,
    "making_inferences": SkillType.INFORMATION_AND_IDEAS,
    "inferencing": SkillType.INFORMATION_AND_IDEAS,
    "main_idea": SkillType.INFORMATION_AND_IDEAS,
    "author_purpose": SkillType.RHETORIC,
    "author_s_purpose": SkillType.RHETORIC,
    "text_structure": SkillType.RHETORIC,
    "vocabulary": SkillType.VOCABULARY_IN_CONTEXT,
    "reading_comprehension": SkillType.INFORMATION_AND_IDEAS,
    "comprehension": SkillType.INFORMATION_AND_IDEAS,
    "reading": SkillType.INFORMATION_AND_IDEAS,
    "close_reading": SkillType.INFORMATION_AND_IDEAS,
    "evidence": SkillType.COMMAND_OF_EVIDENCE,
    "synthesis": SkillType.SYNTHESIS,
    "rhetorical_analysis": SkillType.RHETORIC,
    "word_choice": SkillType.VOCABULARY_IN_CONTEXT,
    "explicit_information": SkillType.COMMAND_OF_EVIDENCE,
    "detail_extraction": SkillType.COMMAND_OF_EVIDENCE,
    # Writing module sub-skills (conventions of standard English)
    "punctuation": SkillType.CONVENTIONS_OF_STANDARD_ENGLISH,
    "tenses": SkillType.CONVENTIONS_OF_STANDARD_ENGLISH,
    "usage": SkillType.CONVENTIONS_OF_STANDARD_ENGLISH,
    "sentence_formation": SkillType.SENTENCE_FORMATION,
    "placement": SkillType.SENTENCE_FORMATION,
    "add_delete": SkillType.SENTENCE_FORMATION,
    "transitions": SkillType.SENTENCE_FORMATION,
    "organization": SkillType.SENTENCE_FORMATION,
    "grammar": SkillType.CONVENTIONS_OF_STANDARD_ENGLISH,
    "graph_interpreting_data": SkillType.GRAPH,
}


def _repair_distractor_roles(choices: List[AnswerChoice]) -> List[AnswerChoice]:
    """Ensure exactly one BEST_ANSWER, one GOOD_NOT_BEST, two COMPLETELY_WRONG.

    Auto-repairs common LLM failures: missing/extra GOOD_NOT_BEST or
    doubled BEST_ANSWER, rather than rejecting the whole question.
    """
    roles = [c.distractor_role for c in choices]
    best = roles.count(DistractorRole.BEST_ANSWER)
    good = roles.count(DistractorRole.GOOD_NOT_BEST)
    wrong = roles.count(DistractorRole.COMPLETELY_WRONG)

    # Fix doubled BEST_ANSWER (2 best, 0 good, 2 wrong) → demote one best to good
    if best == 2 and good == 0 and wrong == 2:
        patched = []
        for c in choices:
            if c.distractor_role == DistractorRole.BEST_ANSWER and not any(
                p.distractor_role == DistractorRole.GOOD_NOT_BEST for p in patched
            ):
                patched.append(c.model_copy(update={"distractor_role": DistractorRole.GOOD_NOT_BEST}))
            else:
                patched.append(c)
        return patched

    # Fix missing BEST_ANSWER (0 best) → promote one wrong to best, then fix good
    if best == 0 and wrong >= 2:
        patched = []
        for c in choices:
            done_best = any(p.distractor_role == DistractorRole.BEST_ANSWER for p in patched)
            done_good = any(p.distractor_role == DistractorRole.GOOD_NOT_BEST for p in patched)
            if not done_best and c.distractor_role == DistractorRole.COMPLETELY_WRONG:
                patched.append(c.model_copy(update={"distractor_role": DistractorRole.BEST_ANSWER}))
            elif not done_good and c.distractor_role == DistractorRole.COMPLETELY_WRONG:
                patched.append(c.model_copy(update={"distractor_role": DistractorRole.GOOD_NOT_BEST}))
            else:
                patched.append(c)
        return patched

    if best != 1:
        return choices

    # Fix missing GOOD_NOT_BEST (1 best, 0 good, 3 wrong) → promote one wrong
    if good == 0 and wrong >= 1:
        patched = []
        for c in choices:
            if c.distractor_role == DistractorRole.COMPLETELY_WRONG and not any(
                p.distractor_role == DistractorRole.GOOD_NOT_BEST for p in patched
            ):
                patched.append(c.model_copy(update={"distractor_role": DistractorRole.GOOD_NOT_BEST}))
            else:
                patched.append(c)
        return patched

    # Fix excess GOOD_NOT_BEST (1 best, 2+ good) → demote extras to wrong
    if good > 1:
        promoted = 0
        patched = []
        for c in choices:
            if c.distractor_role == DistractorRole.GOOD_NOT_BEST and promoted < good - 1:
                patched.append(c.model_copy(update={"distractor_role": DistractorRole.COMPLETELY_WRONG}))
                promoted += 1
            else:
                patched.append(c)
        return patched

    return choices


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

    @field_validator("distractor_role", mode="before")
    @classmethod
    def coerce_distractor_role(cls, v: object) -> object:
        """Coerce LLM string output to DistractorRole enum before strict validation."""
        if isinstance(v, str):
            try:
                return DistractorRole(v)
            except ValueError:
                pass
        return v


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
        return _repair_distractor_roles(choices)

    def __repr__(self) -> str:
        return (
            f"GeneratedQuestion(id={self.id!r}, module={self.module_number}, "
            f"slot={self.slot_number}, difficulty={self.difficulty.value!r})"
        )


class LLMQuestionOutput(BaseModel):
    """Raw LLM output for a single EST question.

    This is the JSON structure the LLM must produce for each question.
    System-assigned fields (id, passage_id, module_number, slot_number,
    question_number) are added later by the generation loop / assembler.
    """

    model_config = ConfigDict(strict=True)

    question_text: str = Field(..., description="The question prompt")
    choices: List[AnswerChoice] = Field(
        ..., min_length=4, max_length=4, description="Four answer choices (A-D)"
    )
    correct_answer: str = Field(
        ..., pattern="^[A-D]$", description="Correct choice letter"
    )
    explanation: str = Field(..., description="Why the correct answer is right")
    supporting_line: str = Field(
        ..., description="Substring of the passage that supports the answer"
    )
    skill_type: SkillType = Field(..., description="Skill being assessed")
    difficulty: Difficulty = Field(..., description="Relative difficulty")

    @field_validator("skill_type", mode="before")
    @classmethod
    def coerce_skill_type(cls, v: object) -> object:
        """Coerce LLM string to SkillType enum before strict validation.

        Handles both exact enum values (``information_and_ideas``) and
        human-readable forms from the prompt (``Information and Ideas``).
        Also maps common LLM-invented skill names via ``_SKILL_FALLBACK_MAP``.
        Falls back to INFORMATION_AND_IDEAS when nothing matches.
        """
        if isinstance(v, str):
            try:
                return SkillType(v)
            except ValueError:
                pass
            # Try normalized (lowercase, spaces → underscores)
            normalized = v.lower().replace(" ", "_").replace("-", "_")
            try:
                return SkillType(normalized)
            except ValueError:
                pass
            # Try fallback map for invented skill names
            if normalized in _SKILL_FALLBACK_MAP:
                return _SKILL_FALLBACK_MAP[normalized]
        return SkillType.INFORMATION_AND_IDEAS

    @field_validator("difficulty", mode="before")
    @classmethod
    def coerce_difficulty(cls, v: object) -> object:
        """Coerce LLM string to Difficulty enum before strict validation.
        Falls back to MEDIUM when nothing matches.
        """
        if isinstance(v, str):
            try:
                return Difficulty(v)
            except ValueError:
                pass
        return Difficulty.MEDIUM

    @field_validator("choices")
    @classmethod
    def validate_distractor_roles(cls, choices: List[AnswerChoice]) -> List[AnswerChoice]:
        return _repair_distractor_roles(choices)

    def __repr__(self) -> str:
        return (
            f"LLMQuestionOutput(skill={self.skill_type.value!r}, "
            f"difficulty={self.difficulty.value!r})"
        )


class LLMBatchOutput(BaseModel):
    """LLM output for a batch of questions on a single passage.

    The LLM returns a top-level ``reasoning`` (chain-of-thought) followed
    by a ``questions`` array.  Each question conforms to LLMQuestionOutput.
    """

    model_config = ConfigDict(strict=True, use_enum_values=True)

    reasoning: str = Field(
        default="",
        description="Chain-of-thought reasoning about the passage and question design",
    )
    questions: List[LLMQuestionOutput] = Field(
        ..., min_length=1, description="Generated questions for this passage"
    )

    def __repr__(self) -> str:
        return f"LLMBatchOutput(questions={len(self.questions)})"


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