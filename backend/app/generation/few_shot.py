"""
EST Synthesizer — Hand-curated Few-Shot Examples (T17)

These examples are hand-written based on the EST skill taxonomy. They get
injected into ``build_user_prompt`` so the LLM can pattern-match the
expected output structure (4 choices with one each of best_answer /
good_not_best / completely_wrong, correct answer, supporting line, etc.)
and the expected writing style (formal register, one BEST per question,
NO CHANGE in the writing module, etc.).

The real long-term fix is to bootstrap from a real EST test bank
(plan task P1: waiting on the teacher friend). Until that lands, these
hand-crafted examples are the best signal we can give the LLM.

Each example is a dict matching the LLMQuestionOutput schema. They are
deliberately terse — they're in-context examples, not full passages for
inference.
"""
from __future__ import annotations

from typing import List

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
    """Return the curated default few-shot examples.

    The LLM sees these at the top of every user prompt as in-context
    examples. They cover the two main shapes:
    - Writing module: NO CHANGE choice + 3 alternatives
    - Reading module: 4 distinct distractors with one clear main idea
    """
    return [dict(ex) for ex in DEFAULT_FEW_SHOT_EXAMPLES]
