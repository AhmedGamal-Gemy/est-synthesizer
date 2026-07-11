"""
EST Synthesizer — Prompt Builder Functions for Question Generation
==================================================================

Builder functions that assemble system and user prompts for LLM calls.
Constants (SYSTEM_PROMPT, WRITING_ADDON, SKILL_TYPE_DESCRIPTIONS)
are defined in backend.app.generation.constants.
"""

from __future__ import annotations

import re
import structlog
from typing import List, Optional

from backend.app.generation.constants import SYSTEM_PROMPT, WRITING_ADDON, SKILL_TYPE_DESCRIPTIONS
from backend.app.generation.few_shot import get_default_few_shot
from backend.app.schemas.enums import ModuleType, SkillType
from backend.app.schemas.passage import Passage
from backend.app.schemas.test import ModuleSlot

logger = structlog.get_logger(__name__)

# ponytail: pick 2 short sentences from the writing-module passage and call
# them out as the "underlined portions" the LLM should ask about. The
# original passage text is sent unmodified so the supporting_line check
# (substring of passage text) still works without a denoising pass.
WRITING_UNDERLINED_PORTIONS = 2
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _pick_underlined_portions(text: str, n: int) -> List[str]:
    """Return up to n short sentences from *text* to use as writing-module targets."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]
    # Prefer sentences in the 30-180 char range — short enough to be a
    # focused editing target, long enough to be a real sentence.
    candidates = [s for s in sentences if 30 <= len(s) <= 180]
    if len(candidates) < n:
        # Fall back to whatever sentences we have, in order
        candidates = sentences
    return candidates[:n]


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------

def build_system_prompt() -> str:
    """Return the static system prompt.

    The system prompt is constant across all requests — it establishes
    role, rules, style notes, and output format. Per-request specificity
    comes from the user prompt.
    """
    logger.debug("Returning static system prompt")
    return SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# build_user_prompt
# ---------------------------------------------------------------------------

def build_user_prompt(
    passage: Passage,
    few_shot_examples: Optional[List[dict]] = None,
    slot_config: ModuleSlot = None,  # type: ignore[assignment]
    module_type: ModuleType = ModuleType.READING_SHORT,
    questions_already_generated: int = 0,
) -> str:
    """Assemble the per-request user prompt from XML sections.

    Parameters
    ----------
    passage : Passage
        The source passage object (from schemas.passage).
    few_shot_examples : Optional[List[dict]]
        Example questions for in-context learning. Each dict should
        contain keys matching LLMQuestionOutput fields. When ``None``
        (the default), the curated examples from
        :func:`backend.app.generation.few_shot.get_default_few_shot`
        are used so every prompt is grounded in concrete examples.
    slot_config : ModuleSlot
        The slot being processed — defines skill_type, difficulty,
        and question_count for this batch.

    Note
    ----
    Each ModuleSlot holds exactly one SkillType; multi-skill coverage
    at the module level comes from multiple slots per module, not from
    mixing skills within a single slot. This keeps per-batch LLM
    instructions unambiguous.

    module_type : ModuleType
        One of: WRITING, READING_LONG, READING_SHORT.
        Determines whether WRITING_ADDON is injected.
    questions_already_generated : int
        Number of questions already produced in prior slots for this
        passage. Used for CURRENT_STATE progress tracking.

    Returns
    -------
    str
        The assembled user prompt with XML-delimited sections.
    """

    if few_shot_examples is None:
        few_shot_examples = get_default_few_shot()

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

    # ── 1b. UNDERLINED_PORTIONS (writing module only) ───────────────────
    # ponytail: writing-module questions need a real "underlined" target.
    # Pick 2 short sentences from the passage and list them as the
    # portions the LLM should ask about. The passage itself is sent
    # unmodified so the supporting_line check (substring of passage) works.
    if module_type == ModuleType.WRITING:
        portions = _pick_underlined_portions(passage.text, WRITING_UNDERLINED_PORTIONS)
        if portions:
            portions_block = "<UNDERLINED_PORTIONS>\n"
            for i, portion in enumerate(portions, start=1):
                portions_block += f"[{i}] {portion}\n"
            portions_block += "</UNDERLINED_PORTIONS>"
            sections.append(portions_block)

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
    task_block += f"Difficulty Distribution: {slot_config.easy_count} easy, {slot_config.medium_count} medium, {slot_config.hard_count} hard\n"
    task_block += "Distractor integrity — For the good_not_best choice: you MUST explain in the reasoning field exactly why it is definitively worse than the best_answer. Cite the specific passage evidence that rules it out. If you cannot articulate a clear, passage-supported reason why it is inferior, choose a different distractor. Two choices that can both be reasonably argued as correct is a generation failure.\n"

    if module_type == ModuleType.WRITING:
        task_block += f"\n{WRITING_ADDON}\n"

    task_block += "</TASK>"
    sections.append(task_block)

    # ── 4. CURRENT_STATE ────────────────────────────────────────────────
    remaining = max(0, count - questions_already_generated)
    state_block = "<CURRENT_STATE>\n"
    state_block += f"Slot Position: {slot_config.slot_number}\n"
    state_block += f"Questions Already Generated for This Passage: {questions_already_generated}\n"
    state_block += f"Questions Remaining in This Slot: {remaining}\n"
    state_block += "</CURRENT_STATE>"
    sections.append(state_block)

    # ── 5. FIGURE_DATA (conditional) ────────────────────────────────────
    if slot_config.has_figure and passage.figure is not None:
        figure_block = "<FIGURE_DATA>\n"
        figure_block += "A figure accompanies this passage. Reference it when relevant.\n"
        figure_block += f"Figure caption: {passage.figure.caption}\n"
        figure_block += f"Figure description: {passage.figure.description}\n"
        if passage.figure.data:
            figure_block += f"Figure content: {passage.figure.data}\n"
        figure_block += "</FIGURE_DATA>"
        sections.append(figure_block)
        logger.debug("Including figure data", caption=passage.figure.caption)

    logger.debug("Built user prompt", skill=slot_config.skill_type.value, difficulty=slot_config.difficulty.value, count=count, remaining=remaining)

    return "\n\n".join(sections)

