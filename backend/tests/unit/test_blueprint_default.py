"""Unit tests for backend.app.blueprint.default — built-in blueprints."""

import json

from backend.app.blueprint.default import (
    DEFAULT_BLUEPRINT,
    DEFAULT_DIFFICULTY,
    HARDER_BLUEPRINT,
    HARDER_DIFFICULTY,
    MODULE_1_SLOTS,
    MODULE_2_SLOTS,
    MODULE_3_SLOTS,
    _make_blueprint,
)
from backend.app.schemas import Difficulty, ModuleConfig, SkillType, TestBlueprint


# ── Blueprint top-level properties ────────────────────────────


class TestBlueprintProperties:
    """Verify id, total_questions, and module count."""

    def test_default_total_questions(self):
        assert DEFAULT_BLUEPRINT.total_questions == 85

    def test_harder_total_questions(self):
        assert HARDER_BLUEPRINT.total_questions == 85

    def test_default_id(self):
        assert DEFAULT_BLUEPRINT.id == "default_blueprint_v1"

    def test_harder_id(self):
        assert HARDER_BLUEPRINT.id == "harder_blueprint_v1"

    def test_default_has_three_modules(self):
        assert len(DEFAULT_BLUEPRINT.modules) == 3

    def test_harder_has_three_modules(self):
        assert len(HARDER_BLUEPRINT.modules) == 3

    def test_default_blueprint_type(self):
        assert isinstance(DEFAULT_BLUEPRINT, TestBlueprint)

    def test_harder_blueprint_type(self):
        assert isinstance(HARDER_BLUEPRINT, TestBlueprint)


# ── Module question counts ────────────────────────────────────


class TestModuleQuestionCounts:
    """Each module's question_count must match its slot sums."""

    def test_module1_question_count(self):
        m = DEFAULT_BLUEPRINT.modules[0]
        assert m.question_count == 35

    def test_module2_question_count(self):
        m = DEFAULT_BLUEPRINT.modules[1]
        assert m.question_count == 25

    def test_module3_question_count(self):
        m = DEFAULT_BLUEPRINT.modules[2]
        assert m.question_count == 25

    def test_module1_slots_sum_to_35(self):
        total = sum(slot.question_count for slot in MODULE_1_SLOTS)
        assert total == 35

    def test_module2_slots_sum_to_25(self):
        total = sum(slot.question_count for slot in MODULE_2_SLOTS)
        assert total == 25

    def test_module3_slots_sum_to_25(self):
        total = sum(slot.question_count for slot in MODULE_3_SLOTS)
        assert total == 25


# ── Module-level flags ────────────────────────────────────────


class TestModuleFlags:
    """wordy_answer_style and has_figure flags per module."""

    def test_module1_wordy_answer_style(self):
        assert DEFAULT_BLUEPRINT.modules[0].wordy_answer_style is True

    def test_module2_has_figure(self):
        assert DEFAULT_BLUEPRINT.modules[1].has_figure is True

    def test_module2_wordy_answer_style_false(self):
        assert DEFAULT_BLUEPRINT.modules[1].wordy_answer_style is False

    def test_module3_has_figure_false(self):
        assert DEFAULT_BLUEPRINT.modules[2].has_figure is False

    def test_module3_wordy_answer_style_false(self):
        assert DEFAULT_BLUEPRINT.modules[2].wordy_answer_style is False

    def test_module1_has_figure_false(self):
        assert DEFAULT_BLUEPRINT.modules[0].has_figure is False


# ── Module type & number ──────────────────────────────────────


class TestModuleTypeAndNumber:
    """Module metadata: type strings and module_number values."""

    def test_module1_type(self):
        assert DEFAULT_BLUEPRINT.modules[0].module_type == "writing"

    def test_module2_type(self):
        assert DEFAULT_BLUEPRINT.modules[1].module_type == "reading_long"

    def test_module3_type(self):
        assert DEFAULT_BLUEPRINT.modules[2].module_type == "reading_short"

    def test_module_numbers_are_1_2_3(self):
        nums = [m.module_number for m in DEFAULT_BLUEPRINT.modules]
        assert nums == [1, 2, 3]


# ── Difficulty distributions ──────────────────────────────────


class TestDifficultyDistribution:
    """DEFAULT_DIFFICULTY and HARDER_DIFFICULTY exact values and sums."""

    def test_default_difficulty_values(self):
        assert DEFAULT_DIFFICULTY == {"easy": 0.20, "medium": 0.40, "hard": 0.40}

    def test_harder_difficulty_values(self):
        assert HARDER_DIFFICULTY == {"easy": 0.10, "medium": 0.35, "hard": 0.55}

    def test_default_distribution_sums_to_one(self):
        total = sum(DEFAULT_DIFFICULTY.values())
        assert abs(total - 1.0) < 1e-9

    def test_harder_distribution_sums_to_one(self):
        total = sum(HARDER_DIFFICULTY.values())
        assert abs(total - 1.0) < 1e-9

    def test_blueprint_difficulty_distribution_sums(self):
        """Every blueprint's difficulty_distribution must sum to ≈1.0."""
        for bp in (DEFAULT_BLUEPRINT, HARDER_BLUEPRINT):
            total = sum(bp.difficulty_distribution.values())
            assert abs(total - 1.0) < 1e-9


# ── _make_blueprint id format ────────────────────────────────


class TestMakeBlueprint:
    """_make_blueprint must produce ids in lowercase_underscore_v1 format."""

    def test_id_format_lowercase(self):
        bp = _make_blueprint("DEFAULT_BLUEPRINT", MODULE_3_SLOTS, DEFAULT_DIFFICULTY)
        assert bp.id == "default_blueprint_v1"

    def test_id_format_with_spaces(self):
        bp = _make_blueprint("My Custom Blueprint", MODULE_3_SLOTS, DEFAULT_DIFFICULTY)
        assert bp.id == "my_custom_blueprint_v1"

    def test_id_format_all_caps(self):
        bp = _make_blueprint("HARDER_BLUEPRINT", MODULE_3_SLOTS, HARDER_DIFFICULTY)
        assert bp.id == "harder_blueprint_v1"


# ── JSON serialization ────────────────────────────────────────


class TestBlueprintSerialization:
    """model_dump(mode='json') must produce a valid JSON-serializable dict."""

    def test_default_blueprint_json_dump(self):
        data = DEFAULT_BLUEPRINT.model_dump(mode="json")
        assert isinstance(data, dict)
        assert "id" in data
        assert "modules" in data
        assert "total_questions" in data
        assert "difficulty_distribution" in data

    def test_harder_blueprint_json_dump(self):
        data = HARDER_BLUEPRINT.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["id"] == "harder_blueprint_v1"

    def test_json_dump_is_json_serializable(self):
        """The dict from model_dump(mode='json') must pass json.dumps."""
        data = DEFAULT_BLUEPRINT.model_dump(mode="json")
        serialized = json.dumps(data)
        assert isinstance(serialized, str)
        # Re-parse to confirm round-trip
        parsed = json.loads(serialized)
        assert parsed["total_questions"] == 85
