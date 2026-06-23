"""
EST Synthesizer — Few-Shot Examples (Real Samples + Hand-crafted)

Primary source: real EST test bank extracted from sample PDFs by
``scripts/extract_samples.py``. The extracted JSON lives at
``data/generated/extracted_samples.json`` and is loaded automatically when
available, falling back to hand-curated examples when the file is absent.

Each example is a dict matching the LLMQuestionOutput schema. They are
deliberately terse — they're in-context examples, not full passages for
inference.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

# ── Extracted-samples loader ────────────────────────────────

_EXTRACTED_PATH = Path("data/generated/extracted_samples.json")

# Map extracted (UPPER_CASE) skill types to enum values (snake_case).
_SKILL_TYPE_MAP: dict[str, str] = {
    "STANDARD_ENGLISH_CONVENTIONS": "conventions_of_standard_english",
    "EXPRESSION_OF_IDEAS": "sentence_formation",
    "COMMAND_OF_EVIDENCE": "command_of_evidence",
    "WORDS_IN_CONTEXT": "vocabulary_in_context",
    "EXPRESSION_OF_IDEAS_IN_LITERATURE": "rhetoric",
    "ANALYSIS_IN_HISTORY_SOCIAL_STUDIES": "information_and_ideas",
    "ANALYSIS_IN_SCIENCE": "information_and_ideas",
}


def _convert_choice(c: dict, correct_letter: str) -> dict:
    """Convert extracted choice to LLMQuestionOutput format."""
    return {
        "letter": c["choice_letter"],
        "text": c["choice_text"],
        "distractor_role": "best_answer" if c["choice_letter"] == correct_letter else "completely_wrong",
    }


def _convert_example(ex: dict) -> dict:
    """Convert an extracted-sample dict to LLMQuestionOutput format."""
    correct = ex["correct_answer"]
    choices = [_convert_choice(c, correct) for c in ex["choices"]]
    # Demote the first wrong choice to good_not_best so every question has
    # the required 1 best + 1 good_not_best + 2 completely_wrong mix.
    for c in choices:
        if c["distractor_role"] == "completely_wrong":
            c["distractor_role"] = "good_not_best"
            break

    skill = _SKILL_TYPE_MAP.get(ex["skill_type"], "information_and_ideas")

    return {
        "question_text": ex["question_text"],
        "choices": choices,
        "correct_answer": correct,
        # ponytail: real EST PDFs don't include explanations. A brief
        # placeholder gives the LLM the shape without making up content.
        "explanation": f"This question tests {skill.replace(chr(95), ' ')}.",
        "supporting_line": ex.get("passage_text", "")[:120],
        "skill_type": skill,
        "difficulty": ex.get("difficulty", "medium").lower(),
    }


# ── Filters ─────────────────────────────────────────────────

# Default filter values — override via load_extracted_samples() kwargs.
_DEFAULT_DATE = None        # e.g. "2023-05" — None = all dates
_DEFAULT_FIELD = None       # "literacy_test_i" (writing) / "literacy_test_ii" / None = all
_DEFAULT_LOCATION = None    # "passage_1" / "passage_2" / None = all
_DEFAULT_ATTENDANCE = 3     # max examples per module type

# Min characters for question_text to pass the length filter
_MIN_QUESTION_LEN = 15

# Garbled character patterns that indicate extraction failure
_GARBLED_PATTERNS = [
    "\ufffd",       # Unicode replacement char (OCR failure)
    "�",            # Same, different encoding
]


def _is_clean(text: str) -> bool:
    """Check text for garbled characters."""
    for pat in _GARBLED_PATTERNS:
        if pat in text:
            return False
    return True


def _filter_and_select(
    raw: list[dict],
    date: str | None = None,
    field: str | None = None,
    location: str | None = None,
    attendance: int = 3,
) -> list[dict]:
    """Apply metadata + quality filters and select a diverse subset.

    Parameters
    ----------
    date : str or None
        Only keep questions from this test date (e.g. ``"2023-05"``).
    field : str or None
        ``"literacy_test_i"`` (writing) or ``"literacy_test_ii"`` (reading).
    location : str or None
        ``"passage_1"``, ``"passage_2"``, etc.
    attendance : int
        Max examples per module type (writing / reading).
    """
    # Pass 0: metadata filters
    meta_filtered: list[dict] = []
    for ex in raw:
        if date and ex.get("date") != date:
            continue
        if field and ex.get("field") != field:
            continue
        if location and ex.get("location") != location:
            continue
        meta_filtered.append(ex)

    # Pass 1: quality gates
    clean: list[dict] = []
    for ex in meta_filtered:
        if len(ex.get("choices", [])) != 4:
            continue
        if not _is_clean(ex.get("question_text", "")):
            continue
        if len(ex.get("question_text", "")) < _MIN_QUESTION_LEN:
            continue
        ca = ex.get("correct_answer", "")
        if ca not in ("A", "B", "C", "D"):
            continue
        if not any(c.get("choice_letter") == ca for c in ex["choices"]):
            continue
        if any(not _is_clean(c.get("choice_text", "")) for c in ex["choices"]):
            continue
        clean.append(ex)

    if not clean:
        return []

    # Pass 2: select diverse subset per module
    by_module: dict[str, list[dict]] = {}
    for ex in clean:
        mod = ex.get("section", "reading")
        by_module.setdefault(mod, []).append(ex)

    selected: list[dict] = []
    for _mod, candidates in by_module.items():
        by_skill: dict[str, list[dict]] = {}
        for ex in candidates:
            sk = ex.get("skill_type", "unknown")
            by_skill.setdefault(sk, []).append(ex)
        taken = []
        for skill_examples in by_skill.values():
            taken.append(skill_examples[0])
        if len(taken) < attendance:
            leftovers = [ex for ex in candidates if ex not in taken]
            taken.extend(leftovers[:attendance - len(taken)])
        selected.extend(taken[:attendance])

    return selected


def load_extracted_samples(
    date: str | None = None,
    field: str | None = None,
    location: str | None = None,
    attendance: int = 3,
) -> list[dict] | None:
    """Load real EST samples, filtered by date / field / location / attendance.

    Parameters
    ----------
    date : str or None
        Filter by test date, e.g. ``"2023-05"``.
    field : str or None
        ``"literacy_test_i"`` (writing) or ``"literacy_test_ii"`` (reading).
    location : str or None
        ``"passage_1"``, ``"passage_2"``, etc.
    attendance : int
        Max examples to select per module type (default 3).

    Returns
    -------
    list[dict] or None
        Converted examples in LLMQuestionOutput format, or None if the
        extracted-samples file is missing or empty.
    """
    path = _EXTRACTED_PATH
    if not path.exists():
        return None
    try:
        with open(str(path), encoding="utf-8") as f:
            raw = json.load(f)
        filtered = _filter_and_select(raw, date, field, location, attendance)
        if not filtered:
            return None
        return [_convert_example(ex) for ex in filtered]
    except (json.JSONDecodeError, KeyError, Exception):
        return None


def _load_extracted_samples() -> list[dict] | None:
    """Shorthand — load with default filters (latest date, balanced)."""
    return load_extracted_samples()


# ── Writing-module examples (Module 1) ──────────────────────


WRITING_NO_CHANGE_EXAMPLE: dict = {
    "question_text": "Which choice best maintains the essay's formal tone?",
    "choices": [
        {"letter": "A", "text": "NO CHANGE", "distractor_role": "best_answer"},
        {"letter": "B", "text": "has been really stretched beyond what it can handle", "distractor_role": "completely_wrong"},
        {"letter": "C", "text": "got way too full", "distractor_role": "completely_wrong"},
        {"letter": "D", "text": "cannot handle all the people anymore", "distractor_role": "good_not_best"},
    ],
    "correct_answer": "A",
    "explanation": "\"NO CHANGE\" preserves the formal register consistent with the rest of the passage. The other choices introduce informal or imprecise language.",
    "supporting_line": "have been stretched beyond their original capacity",
    "skill_type": "conventions_of_standard_english",
    "difficulty": "easy",
}


# ponytail: a second, more literal NO CHANGE example. The earlier example
# showed NO CHANGE vs. informal rewrites, which the LLM apparently reads
# as "NO CHANGE is a generic label". This one shows the literal pattern
# the EST actually uses: NO CHANGE as choice A, with the other three
# choices being real grammar/usage variants of the same sentence.
LITERAL_NO_CHANGE_EXAMPLE: dict = {
    "question_text": "Which choice best corrects the underlined portion of the sentence?",
    "choices": [
        {"letter": "A", "text": "NO CHANGE", "distractor_role": "best_answer"},
        {"letter": "B", "text": "The data, which was collected over six months, were published in a peer-reviewed journal.", "distractor_role": "completely_wrong"},
        {"letter": "C", "text": "The data, which were collected over six months, was published in a peer-reviewed journal.", "distractor_role": "completely_wrong"},
        {"letter": "D", "text": "The data which was collected over six months was published in a peer-reviewed journal.", "distractor_role": "good_not_best"},
    ],
    "correct_answer": "A",
    "explanation": "NO CHANGE is correct. \"Data\" is treated as a singular noun in formal scientific writing, so both the verb (\"was\") and the relative clause (\"which was\") agree with it. The alternatives break subject-verb agreement or drop the necessary comma after the introductory clause.",
    "supporting_line": "The data, which was collected over six months, was published in a peer-reviewed journal",
    "skill_type": "conventions_of_standard_english",
    "difficulty": "medium",
}


WRITING_TRANSITION_EXAMPLE: dict = {
    "question_text": "Which transition best connects this sentence to the previous one?",
    "choices": [
        {"letter": "A", "text": "NO CHANGE", "distractor_role": "best_answer"},
        {"letter": "B", "text": "Therefore,", "distractor_role": "completely_wrong"},
        {"letter": "C", "text": "In addition,", "distractor_role": "completely_wrong"},
        {"letter": "D", "text": "As a result,", "distractor_role": "good_not_best"},
    ],
    "correct_answer": "A",
    "explanation": "\"However\" correctly signals a contrast between the cities' efforts and the persistent funding obstacle. \"Therefore\" and \"As a result\" both imply causation that the passage does not assert.",
    "supporting_line": "However, funding remains a persistent obstacle to meaningful progress",
    "skill_type": "logical_introduction",
    "difficulty": "medium",
}


# ── Reading-module examples (Modules 2 + 3) ─────────────────


READING_MAIN_IDEA_EXAMPLE: dict = {
    "question_text": "What is the main idea of the passage?",
    "choices": [
        {"letter": "A", "text": "The Industrial Revolution transformed society through urbanization and new production methods.", "distractor_role": "best_answer"},
        {"letter": "B", "text": "Factories drew workers from rural areas into cities.", "distractor_role": "completely_wrong"},
        {"letter": "C", "text": "Steam power was an important new technology.", "distractor_role": "completely_wrong"},
        {"letter": "D", "text": "The Industrial Revolution began in England.", "distractor_role": "good_not_best"},
    ],
    "correct_answer": "A",
    "explanation": "Choice A captures the central claim that the Revolution transformed society. The other choices are accurate supporting details but not the main idea.",
    "supporting_line": "The Industrial Revolution marked a turning point in human history",
    "skill_type": "information_and_ideas",
    "difficulty": "easy",
}


READING_VOCABULARY_EXAMPLE: dict = {
    "question_text": "As used in the passage, the word \"revolutionary\" most nearly means:",
    "choices": [
        {"letter": "A", "text": "involving violent political overthrow", "distractor_role": "completely_wrong"},
        {"letter": "B", "text": "causing a fundamental change", "distractor_role": "best_answer"},
        {"letter": "C", "text": "occurring in a circular path", "distractor_role": "completely_wrong"},
        {"letter": "D", "text": "historically important to remember", "distractor_role": "good_not_best"},
    ],
    "correct_answer": "B",
    "explanation": "In context, \"revolutionary\" describes a discovery that overturned existing beliefs. \"Causing a fundamental change\" captures this meaning. The other choices use unrelated senses of \"revolutionary\" or \"important.\"",
    "supporting_line": "overturned long-held assumptions about the nature of matter",
    "skill_type": "vocabulary_in_context",
    "difficulty": "medium",
}


READING_EVIDENCE_EXAMPLE: dict = {
    "question_text": "Which choice best describes the function of the second sentence in the passage?",
    "choices": [
        {"letter": "A", "text": "It provides evidence that supports a claim made in the first sentence.", "distractor_role": "best_answer"},
        {"letter": "B", "text": "It introduces a counter-argument to the first sentence.", "distractor_role": "completely_wrong"},
        {"letter": "C", "text": "It summarizes the main point of the entire passage.", "distractor_role": "completely_wrong"},
        {"letter": "D", "text": "It defines a key term used in the first sentence.", "distractor_role": "good_not_best"},
    ],
    "correct_answer": "A",
    "explanation": "The second sentence presents twin-study evidence supporting the claim that language has an innate component. The other choices mischaracterize the sentence's rhetorical function.",
    "supporting_line": "Recent twin studies provide compelling evidence for the innate position",
    "skill_type": "command_of_evidence",
    "difficulty": "hard",
}


# ── Curated default set ────────────────────────────────────
# ponytail: 2 examples by default keeps the prompt small. Real samples
# (P1 from the plan) will replace these with a fuller bank.

DEFAULT_FEW_SHOT_EXAMPLES: List[dict] = [
    LITERAL_NO_CHANGE_EXAMPLE,
    READING_MAIN_IDEA_EXAMPLE,
]


def get_default_few_shot() -> List[dict]:
    """Return few-shot examples for the LLM prompt.

    Priority:
    1. Real EST samples extracted from PDFs (when ``extracted_samples.json``
       exists). Uses balanced 2-per-module defaults.
    2. Falls back to hand-curated examples when no extracted file is present.

    The LLM sees these at the top of every user prompt as in-context
    examples. They cover the two main shapes:
    - Writing module: NO CHANGE choice + 3 alternatives
    - Reading module: 4 distinct distractors with one clear main idea
    """
    real = load_extracted_samples(attendance=2)
    if real is not None:
        return real
    return [dict(ex) for ex in DEFAULT_FEW_SHOT_EXAMPLES]
