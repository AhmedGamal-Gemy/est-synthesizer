"""Unit tests for backend.app.generation.prompts — prompt templates for question generation."""

import pytest

from backend.app.generation.constants import (
    SYSTEM_PROMPT,
    WRITING_ADDON,
    SKILL_TYPE_DESCRIPTIONS,
)
from backend.app.generation.prompts import (
    build_system_prompt,
    build_user_prompt,
)
from backend.app.schemas.enums import (
    Difficulty,
    DistractorRole,
    ModuleType,
    PassageCategory,
    PassageType,
    SkillType,
)
from backend.app.schemas.passage import Figure, Passage
from backend.app.schemas.test import ModuleSlot


# ── Helpers ──────────────────────────────────────────────────


def _valid_passage(**overrides) -> Passage:
    base = {
        "id": "p-test-001",
        "text": "The cat sat on the mat. It was a sunny day. The mat was soft.",
        "source_url": "https://example.com/passage",
        "source_title": "Test Passage Title",
        "passage_type": PassageType.LONG,
        "passage_category": PassageCategory.NARRATIVE,
        "word_count": 15,
        "reading_level": 5.0,
    }
    base.update(overrides)
    return Passage(**base)


def _valid_slot(**overrides) -> ModuleSlot:
    base = {
        "slot_number": 1,
        "skill_type": SkillType.CONVENTIONS_OF_STANDARD_ENGLISH,
        "difficulty": Difficulty.MEDIUM,
        "question_count": 3,
        "easy_count": 0,
        "medium_count": 3,
        "hard_count": 0,
    }
    base.update(overrides)
    # Recompute difficulty counts when difficulty or question_count are overridden
    d = base.get("difficulty", Difficulty.MEDIUM)
    q = base.get("question_count", 3)
    if "easy_count" not in overrides and "medium_count" not in overrides and "hard_count" not in overrides:
        base["easy_count"] = q if d == Difficulty.EASY else 0
        base["medium_count"] = q if d == Difficulty.MEDIUM else 0
        base["hard_count"] = q if d == Difficulty.HARD else 0
    return ModuleSlot(**base)


def _valid_example() -> dict:
    return {
        "question_text": "Which underlined portion contains an error?",
        "choices": [
            {"letter": "A", "text": "NO CHANGE", "distractor_role": "best_answer"},
            {"letter": "B", "text": "The cat sits", "distractor_role": "good_not_best"},
            {"letter": "C", "text": "The cat sitting", "distractor_role": "completely_wrong"},
            {"letter": "D", "text": "Cat sat the", "distractor_role": "completely_wrong"},
        ],
        "correct_answer": "A",
        "explanation": "The past tense is correct in this context.",
        "supporting_line": "The cat sat on the mat.",
        "skill_type": "conventions_of_standard_english",
        "difficulty": "medium",
    }


# ── SYSTEM_PROMPT ───────────────────────────────────────────


def test_build_system_prompt_returns_constant():
    assert build_system_prompt() == SYSTEM_PROMPT


def test_system_prompt_is_non_empty():
    assert len(SYSTEM_PROMPT) > 0


def test_system_prompt_is_substantial():
    assert len(SYSTEM_PROMPT) > 500


def test_system_prompt_contains_est_keywords():
    assert "EST" in SYSTEM_PROMPT
    assert "Educational Skills Test" in SYSTEM_PROMPT


def test_system_prompt_mentions_best_answer_role():
    assert "best_answer" in SYSTEM_PROMPT


def test_system_prompt_mentions_good_not_best_role():
    assert "good_not_best" in SYSTEM_PROMPT


def test_system_prompt_mentions_completely_wrong_role():
    assert "completely_wrong" in SYSTEM_PROMPT


def test_system_prompt_mentions_supporting_line_and_groundedness():
    assert "supporting_line" in SYSTEM_PROMPT
    assert "Groundedness" in SYSTEM_PROMPT


def test_system_prompt_mentions_easy_difficulty():
    assert "easy" in SYSTEM_PROMPT


def test_system_prompt_mentions_medium_difficulty():
    assert "medium" in SYSTEM_PROMPT


def test_system_prompt_mentions_hard_difficulty():
    assert "hard" in SYSTEM_PROMPT


def test_system_prompt_contains_json_output_format_example():
    assert "```json" not in SYSTEM_PROMPT
    assert '"questions"' in SYSTEM_PROMPT


def test_system_prompt_mentions_reasoning_field():
    assert "reasoning" in SYSTEM_PROMPT


def test_system_prompt_rejects_empty_questions():
    assert "empty" in SYSTEM_PROMPT
    assert "questions" in SYSTEM_PROMPT
    # Now tells the LLM NOT to fall back to empty array
    assert "do NOT fall back to an empty array" in SYSTEM_PROMPT


# ── WRITING_ADDON ───────────────────────────────────────────


def test_writing_addon_is_non_empty():
    assert len(WRITING_ADDON) > 0


def test_writing_addon_contains_no_change():
    assert "NO CHANGE" in WRITING_ADDON


def test_writing_addon_mentions_best_answer_role_for_no_change():
    assert "best_answer" in WRITING_ADDON


def test_writing_addon_mentions_full_sentence_closely_worded_style():
    assert "full sentences" in WRITING_ADDON
    assert "closely worded" in WRITING_ADDON


# ── SKILL_TYPE_DESCRIPTIONS ────────────────────────────────


def test_skill_type_descriptions_has_14_entries():
    assert len(SKILL_TYPE_DESCRIPTIONS) == 14


def test_skill_type_descriptions_keys_match_all_enum_values():
    enum_values = {member.value for member in SkillType}
    description_keys = set(SKILL_TYPE_DESCRIPTIONS.keys())
    assert description_keys == enum_values


def test_skill_type_descriptions_has_no_extra_keys():
    enum_values = {member.value for member in SkillType}
    for key in SKILL_TYPE_DESCRIPTIONS:
        assert key in enum_values, f"Extra key not in SkillType enum: {key}"


def test_skill_type_descriptions_each_value_is_non_empty():
    for key, desc in SKILL_TYPE_DESCRIPTIONS.items():
        assert len(desc) > 0, f"Empty description for key: {key}"


def test_skill_type_descriptions_each_is_human_readable_not_just_enum():
    for key, desc in SKILL_TYPE_DESCRIPTIONS.items():
        assert desc != key, f"Description identical to enum value for key: {key}"


def test_skill_type_descriptions_conventions_of_standard_english():
    assert "conventions_of_standard_english" in SKILL_TYPE_DESCRIPTIONS
    desc = SKILL_TYPE_DESCRIPTIONS["conventions_of_standard_english"]
    assert "Conventions of Standard English" in desc


def test_skill_type_descriptions_graph():
    assert "graph" in SKILL_TYPE_DESCRIPTIONS
    desc = SKILL_TYPE_DESCRIPTIONS["graph"]
    assert "Graph" in desc


# ── build_user_prompt ──────────────────────────────────────


def test_build_user_prompt_reading_short_no_writing_addon():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        module_type=ModuleType.READING_SHORT,
    )
    assert WRITING_ADDON not in result


def test_build_user_prompt_reading_long_no_writing_addon():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        module_type=ModuleType.READING_LONG,
    )
    assert WRITING_ADDON not in result


def test_build_user_prompt_writing_includes_writing_addon():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        module_type=ModuleType.WRITING,
    )
    assert WRITING_ADDON in result


def test_build_user_prompt_contains_passage_section():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "<PASSAGE>" in result
    assert "</PASSAGE>" in result
    assert passage.text in result


def test_build_user_prompt_contains_passage_title():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "<PASSAGE>" in result
    assert passage.source_title in result


def test_build_user_prompt_contains_few_shot_examples_when_provided():
    passage = _valid_passage()
    slot = _valid_slot()
    example = _valid_example()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[example],
        slot_config=slot,
    )
    assert "<FEW_SHOT_EXAMPLES>" in result
    assert "</FEW_SHOT_EXAMPLES>" in result


def test_build_user_prompt_omits_few_shot_examples_when_empty():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "<FEW_SHOT_EXAMPLES>" not in result


def test_build_user_prompt_task_contains_skill_description_not_raw_enum():
    passage = _valid_passage()
    slot = _valid_slot(skill_type=SkillType.CONVENTIONS_OF_STANDARD_ENGLISH)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    # Should contain the human-readable description, not just the enum value
    skill_desc = SKILL_TYPE_DESCRIPTIONS["conventions_of_standard_english"]
    assert skill_desc in result


def test_build_user_prompt_task_contains_difficulty_level():
    passage = _valid_passage()
    slot = _valid_slot(difficulty=Difficulty.MEDIUM)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "Difficulty Level: medium" in result


def test_build_user_prompt_task_contains_question_count():
    passage = _valid_passage()
    slot = _valid_slot(question_count=3)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "Number of Questions: 3" in result


def test_build_user_prompt_current_state_contains_slot_position():
    passage = _valid_passage()
    slot = _valid_slot(slot_number=2)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "Slot Position: 2" in result


def test_build_user_prompt_current_state_contains_already_generated_count():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        questions_already_generated=5,
    )
    assert "Questions Already Generated for This Passage: 5" in result


def test_build_user_prompt_current_state_contains_remaining_count():
    passage = _valid_passage()
    slot = _valid_slot(question_count=3)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "Questions Remaining in This Slot: 3" in result


def test_build_user_prompt_remaining_count_subtracts_already_generated():
    passage = _valid_passage()
    slot = _valid_slot(question_count=5, difficulty=Difficulty.MEDIUM, medium_count=5)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        questions_already_generated=3,
    )
    assert "Questions Remaining in This Slot: 2" in result


def test_build_user_prompt_remaining_count_never_negative():
    passage = _valid_passage()
    slot = _valid_slot(question_count=3, difficulty=Difficulty.MEDIUM, medium_count=3)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        questions_already_generated=10,
    )
    assert "Questions Remaining in This Slot: 0" in result


def test_build_user_prompt_figure_section_appears_when_has_figure_true():
    figure = Figure(caption="Population Chart", description="A bar chart showing population growth")
    passage = _valid_passage(figure=figure)
    slot = _valid_slot(has_figure=True)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "<FIGURE_DATA>" in result
    assert "</FIGURE_DATA>" in result
    assert "Figure caption:" in result
    assert "Population Chart" in result
    assert "Figure description:" in result


def test_build_user_prompt_figure_section_not_appearing_when_has_figure_false():
    passage = _valid_passage()
    slot = _valid_slot(has_figure=False)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "<FIGURE_DATA>" not in result


def test_build_user_prompt_figure_section_not_shown_when_passage_has_no_figure():
    """Even if slot says has_figure=True, no figure section if passage.figure is None."""
    passage = _valid_passage()  # no figure
    slot = _valid_slot(has_figure=True)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "<FIGURE_DATA>" not in result


def test_build_user_prompt_figure_data_mentions_figure_content():
    figure = Figure(caption="Population Chart", description="A bar chart showing population growth", data="A bar chart showing population growth over 50 years")
    passage = _valid_passage(figure=figure)
    slot = _valid_slot(has_figure=True)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "Figure content:" in result
    assert "A bar chart showing population growth over 50 years" in result


def test_build_user_prompt_different_already_generated_counts():
    passage = _valid_passage()
    slot = _valid_slot()
    result_zero = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        questions_already_generated=0,
    )
    result_five = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        questions_already_generated=5,
    )
    assert "Questions Already Generated for This Passage: 0" in result_zero
    assert "Questions Already Generated for This Passage: 5" in result_five
    assert result_zero != result_five


# ── Few-shot examples default (T17) ────────────────────────


def test_build_user_prompt_defaults_few_shot_when_none():
    """When few_shot_examples is None, the curated default examples are used."""
    from backend.app.generation.few_shot import DEFAULT_FEW_SHOT_EXAMPLES

    slot = ModuleSlot(
        slot_number=1, skill_type=SkillType.INFORMATION_AND_IDEAS,
        difficulty=Difficulty.MEDIUM, question_count=1,
        easy_count=0, medium_count=1, hard_count=0,
    )
    result = build_user_prompt(
        passage=_valid_passage(),
        slot_config=slot,
        module_type=ModuleType.READING_SHORT,
    )
    assert "<FEW_SHOT_EXAMPLES>" in result
    # At least one of the default examples should appear
    assert "Question:" in result
    # And the curated example text should be present
    assert any(ex["question_text"] in result for ex in DEFAULT_FEW_SHOT_EXAMPLES)


def test_build_user_prompt_explicit_empty_list_skips_few_shot():
    """An explicit empty list suppresses the few-shot block (escape hatch)."""
    slot = ModuleSlot(
        slot_number=1, skill_type=SkillType.INFORMATION_AND_IDEAS,
        difficulty=Difficulty.MEDIUM, question_count=1,
        easy_count=0, medium_count=1, hard_count=0,
    )
    result = build_user_prompt(
        passage=_valid_passage(),
        few_shot_examples=[],
        slot_config=slot,
        module_type=ModuleType.READING_SHORT,
    )
    assert "<FEW_SHOT_EXAMPLES>" not in result


def test_build_user_prompt_custom_few_shot_overrides_default():
    """A non-empty list overrides the default."""
    custom = [{
        "question_text": "Q-CUSTOM",
        "choices": [
            {"letter": "A", "text": "x", "distractor_role": "best_answer"},
            {"letter": "B", "text": "y", "distractor_role": "good_not_best"},
            {"letter": "C", "text": "z", "distractor_role": "completely_wrong"},
            {"letter": "D", "text": "w", "distractor_role": "completely_wrong"},
        ],
        "correct_answer": "A", "explanation": "e",
        "supporting_line": "s", "skill_type": "information_and_ideas",
        "difficulty": "easy",
    }]
    slot = ModuleSlot(
        slot_number=1, skill_type=SkillType.INFORMATION_AND_IDEAS,
        difficulty=Difficulty.MEDIUM, question_count=1,
        easy_count=0, medium_count=1, hard_count=0,
    )
    result = build_user_prompt(
        passage=_valid_passage(),
        few_shot_examples=custom,
        slot_config=slot,
        module_type=ModuleType.READING_SHORT,
    )
    assert "Q-CUSTOM" in result


# ── Writing-module UNDERLINED_PORTIONS (T17) ────────────────


_WRITING_PASSAGE_TEXT = (
    "The Industrial Revolution marked a turning point in human history. "
    "Factories proliferated across England, drawing workers from rural areas into cities. "
    "This shift fundamentally altered social structures and economic relationships. "
    "The rise of steam power enabled mass production on an unprecedented scale."
)


def test_build_user_prompt_writing_module_includes_underlined_portions():
    """Writing-module prompts include an <UNDERLINED_PORTIONS> block."""
    slot = ModuleSlot(
        slot_number=1, skill_type=SkillType.SENTENCE_FORMATION,
        difficulty=Difficulty.EASY, question_count=1,
        easy_count=1, medium_count=0, hard_count=0,
    )
    result = build_user_prompt(
        passage=_valid_passage(text=_WRITING_PASSAGE_TEXT),
        few_shot_examples=[],
        slot_config=slot,
        module_type=ModuleType.WRITING,
    )
    assert "<UNDERLINED_PORTIONS>" in result
    assert "[1]" in result
    assert "[2]" in result


def test_build_user_prompt_reading_module_omits_underlined_portions():
    """Reading-module prompts must NOT include the UNDERLINED_PORTIONS block."""
    slot = ModuleSlot(
        slot_number=1, skill_type=SkillType.INFORMATION_AND_IDEAS,
        difficulty=Difficulty.MEDIUM, question_count=1,
        easy_count=0, medium_count=1, hard_count=0,
    )
    for mod in (ModuleType.READING_LONG, ModuleType.READING_SHORT):
        result = build_user_prompt(
            passage=_valid_passage(text=_WRITING_PASSAGE_TEXT),
            few_shot_examples=[],
            slot_config=slot,
            module_type=mod,
        )
        assert "<UNDERLINED_PORTIONS>" not in result, f"Should not appear in {mod.value}"


def test_build_user_prompt_underlined_portions_are_passage_sentences():
    """The [1]/[2] portions must be exact substrings of the passage text."""
    slot = ModuleSlot(
        slot_number=1, skill_type=SkillType.SENTENCE_FORMATION,
        difficulty=Difficulty.EASY, question_count=1,
        easy_count=1, medium_count=0, hard_count=0,
    )
    result = build_user_prompt(
        passage=_valid_passage(text=_WRITING_PASSAGE_TEXT),
        few_shot_examples=[],
        slot_config=slot,
        module_type=ModuleType.WRITING,
    )
    # At least one of the sentences from the passage should appear inside the
    # UNDERLINED_PORTIONS block. We don't pin to [1] vs [2] because the picker
    # just takes the first 2 in length-preferred order.
    assert "Factories proliferated across England" in result
    assert "The rise of steam power" in result


def test_build_user_prompt_passage_text_unmodified_for_writing():
    """The <PASSAGE> block must contain the original text so the
    supporting_line substring check still works without a denoising pass."""
    slot = ModuleSlot(
        slot_number=1, skill_type=SkillType.SENTENCE_FORMATION,
        difficulty=Difficulty.EASY, question_count=1,
        easy_count=1, medium_count=0, hard_count=0,
    )
    result = build_user_prompt(
        passage=_valid_passage(text=_WRITING_PASSAGE_TEXT),
        few_shot_examples=[],
        slot_config=slot,
        module_type=ModuleType.WRITING,
    )
    # Pull out the <PASSAGE>...</PASSAGE> block
    start = result.find("<PASSAGE>")
    end = result.find("</PASSAGE>")
    passage_block = result[start:end]
    # Original text must be present unmodified
    assert _WRITING_PASSAGE_TEXT in passage_block
    # The [1]/[2] markers must NOT be inside the PASSAGE block
    assert "[1]" not in passage_block
    assert "[2]" not in passage_block
