"""Unit tests for backend.app.generation.prompts — prompt templates for question generation."""

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
    PassageCategory,
    PassageType,
    SkillType,
)
from backend.app.schemas.passage import Passage
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
    }
    base.update(overrides)
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
    assert "```json" in SYSTEM_PROMPT
    assert '"questions"' in SYSTEM_PROMPT


def test_system_prompt_mentions_reasoning_field():
    assert "reasoning" in SYSTEM_PROMPT


def test_system_prompt_contains_error_handling_empty_questions():
    assert "empty" in SYSTEM_PROMPT
    assert "questions" in SYSTEM_PROMPT
    # Check for explicit error handling instructions
    assert "empty `questions` array" in SYSTEM_PROMPT


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
        module_type="reading_short",
    )
    assert WRITING_ADDON not in result


def test_build_user_prompt_reading_long_no_writing_addon():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        module_type="reading_long",
    )
    assert WRITING_ADDON not in result


def test_build_user_prompt_writing_includes_writing_addon():
    passage = _valid_passage()
    slot = _valid_slot()
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
        module_type="writing",
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


def test_build_user_prompt_figure_section_appears_when_has_figure_true():
    passage = _valid_passage()
    slot = _valid_slot(has_figure=True)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "<FIGURE_DATA>" in result
    assert "</FIGURE_DATA>" in result


def test_build_user_prompt_figure_section_not_appearing_when_has_figure_false():
    passage = _valid_passage()
    slot = _valid_slot(has_figure=False)
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "<FIGURE_DATA>" not in result


def test_build_user_prompt_figure_data_mentions_figure_content():
    passage = _valid_passage()
    slot = _valid_slot(has_figure=True, figure_data="A bar chart showing population growth")
    result = build_user_prompt(
        passage=passage,
        few_shot_examples=[],
        slot_config=slot,
    )
    assert "Figure content:" in result
    assert "A bar chart showing population growth" in result


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
