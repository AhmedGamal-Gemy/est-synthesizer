"""Unit tests for backend.app.schemas.enums — LowerStrEnum auto() values and str behaviour."""

from enum import Enum

from backend.app.schemas.enums import (
    Difficulty,
    DistractorRole,
    JobStatus,
    LowerStrEnum,
    PassageCategory,
    PassageType,
    QuestionFlag,
    QuestionType,
    SkillType,
)


# ── PassageType ──────────────────────────────────────────────

def test_passage_type_long_value_is_lowered_name():
    """LowerStrEnum auto() generates lower-cased member name values."""
    assert PassageType.LONG.value == "long"


def test_passage_type_short_value_is_lowered_name():
    assert PassageType.SHORT.value == "short"


def test_passage_type_str_returns_class_dot_name():
    """str(EnumMember) returns 'ClassName.MEMBER_NAME' for (str, Enum)."""
    assert str(PassageType.LONG) == "PassageType.LONG"
    assert str(PassageType.SHORT) == "PassageType.SHORT"


def test_passage_type_all_members_count():
    members = list(PassageType)
    assert len(members) == 2


def test_passage_type_members_are_long_and_short():
    assert set(m.name for m in PassageType) == {"LONG", "SHORT"}


# ── PassageCategory ──────────────────────────────────────────

def test_passage_category_member_names():
    expected = {"ESSAY", "NARRATIVE", "SCIENTIFIC", "HISTORY", "ARGUMENTATIVE"}
    assert set(m.name for m in PassageCategory) == expected


def test_passage_category_auto_values_are_lowered_names():
    values = [m.value for m in PassageCategory]
    expected = ["essay", "narrative", "scientific", "history", "argumentative"]
    assert values == expected


def test_passage_category_str_returns_class_dot_name():
    assert str(PassageCategory.ESSAY) == "PassageCategory.ESSAY"
    assert str(PassageCategory.ARGUMENTATIVE) == "PassageCategory.ARGUMENTATIVE"


def test_passage_category_member_count():
    assert len(list(PassageCategory)) == 5


# ── QuestionType ─────────────────────────────────────────────

def test_question_type_multiple_choice_value():
    assert QuestionType.MULTIPLE_CHOICE.value == "multiple_choice"


def test_question_type_str_returns_class_dot_name():
    assert str(QuestionType.MULTIPLE_CHOICE) == "QuestionType.MULTIPLE_CHOICE"


def test_question_type_all_members():
    members = list(QuestionType)
    assert len(members) == 1


# ── SkillType ────────────────────────────────────────────────

def test_skill_type_member_names():
    expected = {
        "CONVENTIONS_OF_STANDARD_ENGLISH",
        "SENTENCE_FORMATION",
        "PUNCTUATION",
        "USAGE",
        "TENSES",
        "PLACEMENT",
        "ADD_DELETE",
        "LOGICAL_INTRODUCTION",
        "INFORMATION_AND_IDEAS",
        "RHETORIC",
        "SYNTHESIS",
        "VOCABULARY_IN_CONTEXT",
        "COMMAND_OF_EVIDENCE",
        "GRAPH",
    }
    assert set(m.name for m in SkillType) == expected


def test_skill_type_auto_values_are_lowered_names():
    values = [m.value for m in SkillType]
    expected = [m.name.lower() for m in SkillType]
    assert values == expected


def test_skill_type_str_returns_class_dot_name():
    assert str(SkillType.RHETORIC) == "SkillType.RHETORIC"
    assert str(SkillType.GRAPH) == "SkillType.GRAPH"


def test_skill_type_member_count():
    assert len(list(SkillType)) == 14


# ── Difficulty ────────────────────────────────────────────────

def test_difficulty_easy_value():
    assert Difficulty.EASY.value == "easy"


def test_difficulty_medium_value():
    assert Difficulty.MEDIUM.value == "medium"


def test_difficulty_hard_value():
    assert Difficulty.HARD.value == "hard"


def test_difficulty_str_returns_class_dot_name():
    assert str(Difficulty.EASY) == "Difficulty.EASY"
    assert str(Difficulty.HARD) == "Difficulty.HARD"


def test_difficulty_member_count():
    assert len(list(Difficulty)) == 3


# ── DistractorRole ────────────────────────────────────────────

def test_distractor_role_values():
    assert DistractorRole.BEST_ANSWER.value == "best_answer"
    assert DistractorRole.GOOD_NOT_BEST.value == "good_not_best"
    assert DistractorRole.COMPLETELY_WRONG.value == "completely_wrong"


def test_distractor_role_str_returns_class_dot_name():
    assert str(DistractorRole.BEST_ANSWER) == "DistractorRole.BEST_ANSWER"
    assert str(DistractorRole.COMPLETELY_WRONG) == "DistractorRole.COMPLETELY_WRONG"


def test_distractor_role_all_members():
    members = list(DistractorRole)
    assert len(members) == 3


# ── QuestionFlag ──────────────────────────────────────────────

def test_question_flag_member_names():
    expected = {
        "AMBIGUOUS",
        "POORLY_PHRASED",
        "OFF_TOPIC",
        "TOO_EASY",
        "TOO_HARD",
        "INCORRECT_ANSWER",
        "UNCLEAR_DISTRACTORS",
        "FACTUALLY_INCORRECT",
    }
    assert set(m.name for m in QuestionFlag) == expected


def test_question_flag_auto_values_are_lowered_names():
    values = [m.value for m in QuestionFlag]
    expected = [m.name.lower() for m in QuestionFlag]
    assert values == expected


def test_question_flag_str_returns_class_dot_name():
    assert str(QuestionFlag.AMBIGUOUS) == "QuestionFlag.AMBIGUOUS"
    assert str(QuestionFlag.FACTUALLY_INCORRECT) == "QuestionFlag.FACTUALLY_INCORRECT"


def test_question_flag_member_count():
    assert len(list(QuestionFlag)) == 8


# ── JobStatus ─────────────────────────────────────────────────

def test_job_status_member_names():
    expected = {
        "PENDING",
        "QUEUED",
        "GENERATING",
        "ASSEMBLING",
        "RENDERING",
        "COMPLETED",
        "FAILED",
    }
    assert set(m.name for m in JobStatus) == expected


def test_job_status_auto_values_are_lowered_names():
    values = [m.value for m in JobStatus]
    expected = [m.name.lower() for m in JobStatus]
    assert values == expected


def test_job_status_str_returns_class_dot_name():
    assert str(JobStatus.PENDING) == "JobStatus.PENDING"
    assert str(JobStatus.COMPLETED) == "JobStatus.COMPLETED"
    assert str(JobStatus.FAILED) == "JobStatus.FAILED"


def test_job_status_all_members():
    members = list(JobStatus)
    assert len(members) == 7


# ── All enums are (str, Enum) subclasses ─────────────────────

def test_all_enums_are_lower_str_enum():
    for enum_cls in [
        PassageType, PassageCategory, QuestionType, SkillType,
        Difficulty, DistractorRole, QuestionFlag, JobStatus,
    ]:
        assert issubclass(enum_cls, LowerStrEnum)
        assert issubclass(enum_cls, str)
        assert issubclass(enum_cls, Enum)


def test_all_enum_members_compare_by_identity():
    """Enum members are singletons — identity comparison works."""
    assert PassageType.LONG is PassageType.LONG
    assert Difficulty.EASY is Difficulty.EASY
