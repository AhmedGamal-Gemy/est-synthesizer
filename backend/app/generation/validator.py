"""Validates LLM question output beyond Pydantic schema checks.

Pydantic on ``LLMQuestionOutput`` already covers structural checks
(correct_answer letter, choices length, distractor roles, enum values).
This module checks things the schema cannot: groundedness, empty text, etc.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from backend.app.schemas.question import LLMQuestionOutput


def _fuzzy_supporting_line_match(supporting_line: str, passage_text: str) -> bool:
    """Check supporting line with fuzzy fallback."""
    norm_line = " ".join(supporting_line.split())
    norm_passage = " ".join(passage_text.split())
    if norm_line in norm_passage:
        return True
    # ponytail: fuzzy fallback — if exact fails, try sliding window match
    # The LLM often drops/alters a few words. A ratio > 0.85 saves most of these.
    line_len = len(norm_line.split())
    if line_len < 3:
        return False
    words = norm_passage.split()
    # Try every window of matching length
    for i in range(len(words) - line_len + 1):
        window = " ".join(words[i:i + line_len])
        ratio = SequenceMatcher(None, norm_line, window).ratio()
        if ratio > 0.85:
            return True
    return False


def validate_question(
    output: LLMQuestionOutput,
    passage_text: str,
) -> tuple[bool, list[str]]:
    """Validate a parsed LLM question against the source passage.

    Returns (True, []) if valid, (False, [error messages]) if not.
    """
    errors: list[str] = []

    # ── Choice text emptiness ───────────────────────────────────
    for choice in output.choices:
        if not choice.text.strip():
            errors.append(f"Choice {choice.letter} text is empty")

    # ── Supporting-line groundedness ────────────────────────────
    if not output.supporting_line:
        errors.append("supporting_line is empty")
    elif not _fuzzy_supporting_line_match(output.supporting_line, passage_text):
        errors.append(
            "supporting_line is not a substring of the passage text"
        )

    # ── Correct-answer / choice cross-check ─────────────────────
    choice_letters = {c.letter for c in output.choices}
    if output.correct_answer not in choice_letters:
        errors.append(
            f"correct_answer '{output.correct_answer}' "
            f"does not match any choice letter ({sorted(choice_letters)})"
        )

    return (len(errors) == 0, errors)
