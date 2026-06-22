"""Validates LLM question output beyond Pydantic schema checks.

Pydantic on ``LLMQuestionOutput`` already covers structural checks
(correct_answer letter, choices length, distractor roles, enum values).
This module checks things the schema cannot: groundedness, empty text, etc.
"""

from __future__ import annotations

from backend.app.schemas.question import LLMQuestionOutput


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
    # ponytail: normalized substring match; upgrade to fuzzy/embedding if needed
    if not output.supporting_line:
        errors.append("supporting_line is empty")
    else:
        # Normalize whitespace on both sides — LLMs often add/omit spaces
        norm_line = " ".join(output.supporting_line.split())
        norm_passage = " ".join(passage_text.split())
        if norm_line not in norm_passage:
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
