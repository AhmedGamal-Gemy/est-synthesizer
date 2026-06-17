"""
EST Synthesizer — Prompt Builder Functions for Question Generation
==================================================================

Builder functions that assemble system and user prompts for LLM calls.
Constants (SYSTEM_PROMPT, WRITING_ADDON, SKILL_TYPE_DESCRIPTIONS)
are defined in backend.app.generation.constants.
"""

from __future__ import annotations

from typing import List, Optional, Union

from backend.app.generation.constants import SYSTEM_PROMPT, WRITING_ADDON, SKILL_TYPE_DESCRIPTIONS
from backend.app.schemas.enums import Difficulty, DistractorRole, SkillType
from backend.app.schemas.passage import Passage
from backend.app.schemas.question import LLMBatchOutput, LLMQuestionOutput
from backend.app.schemas.test import ModuleSlot

# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------

def build_system_prompt() -> str:
    """Return the static system prompt.

    The system prompt is constant across all requests — it establishes
    role, rules, style notes, and output format. Per-request specificity
    comes from the user prompt.
    """
    return SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# build_user_prompt
# ---------------------------------------------------------------------------

def build_user_prompt(
    passage: Passage,
    few_shot_examples: List[dict],
    slot_config: ModuleSlot,
    module_type: str = "reading_short",
    questions_already_generated: int = 0,
) -> str:
    """Assemble the per-request user prompt from XML sections.

    Parameters
    ----------
    passage : Passage
        The source passage object (from schemas.passage).
    few_shot_examples : List[dict]
        Example questions for in-context learning. Each dict should
        contain keys matching LLMQuestionOutput fields.
    slot_config : ModuleSlot
        The slot being processed — defines skill_type, difficulty,
        and question_count for this batch.
    module_type : str
        One of: "writing", "reading_long", "reading_short".
        Determines whether WRITING_ADDON is injected.
    questions_already_generated : int
        Number of questions already produced in prior slots for this
        passage. Used for CURRENT_STATE progress tracking.

    Returns
    -------
    str
        The assembled user prompt with XML-delimited sections.
    """

    sections: list[str] = []

    # ── 1. PASSAGE ──────────────────────────────────────────────────────
    passage_block = f"<PASSAGE>\n"
    if passage.source_title:
        passage_block += f"Title: {passage.source_title}\n"
    passage_block += f"Type: {passage.passage_type.value}\n"
    if passage.passage_category:
        passage_block += f"Category: {passage.passage_category.value}\n"
    passage_block += f"\n{passage.text}\n</PASSAGE>"
    sections.append(passage_block)

    # ── 2. FEW_SHOT_EXAMPLES ────────────────────────────────────────────
    if few_shot_examples:
        examples_block = "<FEW_SHOT_EXAMPLES>\n"
        for idx, ex in enumerate(few_shot_examples, start=1):
            examples_block += f"\n--- Example {idx} ---\n"
            examples_block += f"Question: {ex.get('question_text', '')}\n"
            # Format choices
            choices = ex.get("choices", [])
            for ch in choices:
                letter = ch.get("letter", "")
                text = ch.get("text", "")
                role = ch.get("distractor_role", "")
                examples_block += f"  {letter}) {text} [{role}]\n"
            examples_block += f"Correct Answer: {ex.get('correct_answer', '')}\n"
            examples_block += f"Explanation: {ex.get('explanation', '')}\n"
            examples_block += f"Supporting Line: {ex.get('supporting_line', '')}\n"
            examples_block += f"Skill: {ex.get('skill_type', '')}\n"
            examples_block += f"Difficulty: {ex.get('difficulty', '')}\n"
        examples_block += "\n</FEW_SHOT_EXAMPLES>"
        sections.append(examples_block)

    # ── 3. TASK ─────────────────────────────────────────────────────────
    skill_value = slot_config.skill_type.value
    skill_desc = SKILL_TYPE_DESCRIPTIONS.get(
        skill_value, skill_value
    )
    difficulty_value = slot_config.difficulty.value
    count = slot_config.question_count

    task_block = "<TASK>\n"
    task_block += f"Skill Type: {skill_desc}\n"
    task_block += f"Difficulty Level: {difficulty_value}\n"
    task_block += f"Number of Questions: {count}\n"

    if module_type == "writing":
        task_block += f"\n{WRITING_ADDON}\n"

    task_block += "</TASK>"
    sections.append(task_block)

    # ── 4. CURRENT_STATE ────────────────────────────────────────────────
    remaining = count
    state_block = "<CURRENT_STATE>\n"
    state_block += f"Slot Position: {slot_config.slot_number}\n"
    state_block += f"Questions Already Generated for This Passage: {questions_already_generated}\n"
    state_block += f"Questions Remaining in This Slot: {remaining}\n"
    state_block += "</CURRENT_STATE>"
    sections.append(state_block)

    # ── 5. FIGURE_DATA (conditional) ────────────────────────────────────
    if slot_config.has_figure:
        figure_block = "<FIGURE_DATA>\n"
        figure_block += "A figure accompanies this passage. Reference it when relevant.\n"
        if slot_config.figure_data:
            figure_block += f"Figure content: {slot_config.figure_data}\n"
        figure_block += "</FIGURE_DATA>"
        sections.append(figure_block)

    return "\n\n".join(sections)
