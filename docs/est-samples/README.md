# Real EST Samples (P1 from the plan)

This directory is for the real EST test PDFs the teacher friend shared.
**The PDFs themselves are gitignored** — drop them here locally, but they
should not end up in git history. The reason: the samples are
teacher-shared material that the project doesn't need to redistribute.

## What to put here

- One or more `.pdf` files containing real EST test samples
- Filenames like `est-sample-2023.pdf`, `est-sample-2024.pdf`, etc.

## How the pipeline uses them

Once a sample lands here, the extractor (`scripts/extract_samples.py`,
written when the first file arrives) parses the question structure and
feeds it into `backend/app/generation/few_shot.py` as additional
in-context examples for the LLM. The hand-crafted examples currently in
that file stay as a fallback; the real samples take priority when present.

## What gets extracted

Per question, the extractor tries to pull:
- `question_text`
- 4 answer choices (A-D)
- `correct_answer` (the letter of the right choice)
- The skill the question is testing (inferred if not labeled)

What it does NOT need:
- `explanation` (the LLM writes its own)
- `supporting_line` (the LLM picks from the actual passage)
- `difficulty` (we have our own distribution)
- `distractor_role` for the wrong choices (we infer from the correct answer: 1 good_not_best + 2 completely_wrong)
