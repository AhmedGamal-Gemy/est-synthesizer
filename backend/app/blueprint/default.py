"""
EST Synthesizer - Built-in Blueprint Definitions
=======================================================
Defines the DEFAULT_BLUEPRINT and HARDER_BLUEPRINT used by the
generation pipeline.  Each blueprint is a fully-typed TestBlueprint
instance built from ModuleConfig and ModuleSlot models.

Module 1 — Writing          3 slots / 35 Q / wordy answers
Module 2 — Reading Long     2 slots / 25 Q / has figure
Module 3 — Reading Short   11 slots / 25 Q / alternating passages
                          ─────────────────────
          Total              85 questions
"""

from backend.app.schemas import (
    Difficulty,
    ModuleConfig,
    ModuleSlot,
    SkillType,
    TestBlueprint,
)

# ---------------------------------------------------------------------------
# Difficulty helpers
# ---------------------------------------------------------------------------

_E = Difficulty.EASY
_M = Difficulty.MEDIUM
_H = Difficulty.HARD

# ---------------------------------------------------------------------------
# Module 1 — Writing  (wordy_answer_style = True)
# ---------------------------------------------------------------------------

MODULE_1_SLOTS = [
    ModuleSlot(
        slot_number=1,
        skill_type=SkillType.SENTENCE_FORMATION,
        difficulty=_E,
        question_count=5,
    ),
    ModuleSlot(
        slot_number=1,
        skill_type=SkillType.CONVENTIONS_OF_STANDARD_ENGLISH,
        difficulty=_M,
        question_count=7,
    ),
    ModuleSlot(
        slot_number=2,
        skill_type=SkillType.PUNCTUATION,
        difficulty=_M,
        question_count=4,
    ),
    ModuleSlot(
        slot_number=2,
        skill_type=SkillType.TENSES,
        difficulty=_E,
        question_count=4,
    ),
    ModuleSlot(
        slot_number=2,
        skill_type=SkillType.USAGE,
        difficulty=_H,
        question_count=4,
    ),
    ModuleSlot(
        slot_number=3,
        skill_type=SkillType.PLACEMENT,
        difficulty=_M,
        question_count=4,
    ),
    ModuleSlot(
        slot_number=3,
        skill_type=SkillType.ADD_DELETE,
        difficulty=_M,
        question_count=3,
    ),
    ModuleSlot(
        slot_number=3,
        skill_type=SkillType.LOGICAL_INTRODUCTION,
        difficulty=_H,
        question_count=4,
    ),
]

# ---------------------------------------------------------------------------
# Module 2 — Reading Long  (has_figure = True)
# ---------------------------------------------------------------------------

MODULE_2_SLOTS = [
    ModuleSlot(
        slot_number=1,
        skill_type=SkillType.INFORMATION_AND_IDEAS,
        difficulty=_M,
        question_count=5,
        has_figure=True,
    ),
    ModuleSlot(
        slot_number=1,
        skill_type=SkillType.RHETORIC,
        difficulty=_M,
        question_count=4,
    ),
    ModuleSlot(
        slot_number=1,
        skill_type=SkillType.COMMAND_OF_EVIDENCE,
        difficulty=_H,
        question_count=4,
    ),
    ModuleSlot(
        slot_number=2,
        skill_type=SkillType.SYNTHESIS,
        difficulty=_H,
        question_count=4,
    ),
    ModuleSlot(
        slot_number=2,
        skill_type=SkillType.VOCABULARY_IN_CONTEXT,
        difficulty=_E,
        question_count=4,
    ),
    ModuleSlot(
        slot_number=2,
        skill_type=SkillType.GRAPH,
        difficulty=_M,
        question_count=4,
        has_figure=True,
    ),
]

# ---------------------------------------------------------------------------
# Module 3 — Reading Short  (11 alternating slots, 1 passage each)
# ---------------------------------------------------------------------------

MODULE_3_SLOTS = [
    ModuleSlot(slot_number=s, skill_type=st, difficulty=d, question_count=q)
    for s, st, d, q in [
        (1, SkillType.VOCABULARY_IN_CONTEXT, _E, 2),
        (2, SkillType.COMMAND_OF_EVIDENCE, _M, 3),
        (3, SkillType.GRAPH, _M, 2),
        (4, SkillType.INFORMATION_AND_IDEAS, _M, 2),
        (5, SkillType.RHETORIC, _H, 3),
        (6, SkillType.SYNTHESIS, _H, 2),
        (7, SkillType.VOCABULARY_IN_CONTEXT, _E, 2),
        (8, SkillType.COMMAND_OF_EVIDENCE, _M, 2),
        (9, SkillType.INFORMATION_AND_IDEAS, _H, 3),
        (10, SkillType.GRAPH, _M, 2),
        (11, SkillType.RHETORIC, _E, 2),
    ]
]

# ---------------------------------------------------------------------------
# Blueprint builders
# ---------------------------------------------------------------------------

DEFAULT_DIFFICULTY = {"easy": 0.20, "medium": 0.40, "hard": 0.40}
HARDER_DIFFICULTY = {"easy": 0.10, "medium": 0.35, "hard": 0.55}


def _make_blueprint(
    name: str,
    module_3_slots: list[ModuleSlot],
    difficulty_dist: dict,
) -> TestBlueprint:
    modules = [
        ModuleConfig(
            module_number=1,
            module_type="writing",
            slots=MODULE_1_SLOTS,
            has_figure=False,
            wordy_answer_style=True,
        ),
        ModuleConfig(
            module_number=2,
            module_type="reading_long",
            slots=MODULE_2_SLOTS,
            has_figure=True,
            wordy_answer_style=False,
        ),
        ModuleConfig(
            module_number=3,
            module_type="reading_short",
            slots=module_3_slots,
            has_figure=False,
            wordy_answer_style=False,
        ),
    ]
    total = sum(m.question_count for m in modules)
    return TestBlueprint(
        id=f"{name.lower().replace(' ', '_')}_v1",
        name=name,
        modules=modules,
        total_questions=total,
        difficulty_distribution=difficulty_dist,
    )


DEFAULT_BLUEPRINT: TestBlueprint = _make_blueprint(
    "DEFAULT_BLUEPRINT",
    MODULE_3_SLOTS,
    DEFAULT_DIFFICULTY,
)

HARDER_BLUEPRINT: TestBlueprint = _make_blueprint(
    "HARDER_BLUEPRINT",
    MODULE_3_SLOTS,
    HARDER_DIFFICULTY,
)
