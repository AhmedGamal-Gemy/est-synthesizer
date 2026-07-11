# EST Material Synthesizer — Full Development Plan
> Last updated: July 2026
> Status: MVP pipeline working, 72/85 questions generated E2E

---

## Current Situation

### What works
- Full pipeline runs end-to-end: scrape → embed → retrieve → generate → assemble → PDF
- 509 passages in Qdrant (330 short, 179 long) — above cold start threshold
- 494/497 unit tests passing
- 57 commits, solid foundation
- Blueprint system: DEFAULT + HARDER variants, full REST CRUD
- SQLite: jobs, inventory, feedback tables
- SSE progress streaming works
- FastAPI backend fully routed
- Student + teacher PDF rendering (figures placeholder only)

### Teacher feedback (first real test review)
| # | Feedback (Arabic) | Meaning | Maps to |
|---|---|---|---|
| 1 | اسئله متكرره | Repetitive questions — same fact tested twice | B7 (line coverage), B2 (per-difficulty few-shots) |
| 2 | غلطات في الجرامر | Grammar mistakes in question text / answer choices | B8 (grammar prompt fix) |
| 3 | تناقض في الاجابات | Contradictions between answer choices | E1 (RoBERTa) — promoted to Sprint 2 |
| 4 | التيكست نفسه حلو | Passage quality is good ✅ | No change needed |
| 5 | اول سؤال كان كويس جداً، صعوبة متوسطة | First question was excellent, medium difficulty ✅ | Generation is viable |
| 6 | الاسئله لازم تتوزع على القطعة | Questions must spread across the passage, not cluster on one line | B7 (new task) |

---

### What's broken
| Bug | File | Impact |
|---|---|---|
| LLM enum coercion drops 13/85 questions | `generation/validator.py` + `LLMBatchOutput` | 84% yield instead of 100% |
| 3 async test failures | `test_generate_test_cli.py` | CI broken |
| Intra-run passage dedup missing | `generation/loop.py` | Same passage appears twice in one test |
| Gutendex 403 (worked around) | `scraper/gutenberg.py` | Bootstrap uses fragile direct-download |
| Qdrant Docker unstable on Windows | `docker-compose.yml` | Container crashes mid-session |

### What's missing (from full plan)
- **Grammar quality enforcement in prompt** ← teacher flagged (B8)
- **Passage line coverage tracking — question distribution** ← teacher flagged (B7)
- **Answer contradiction detection** ← teacher flagged (E1, promoted to Sprint 2)
- Per-difficulty few-shot selection
- Scope mismatch instruction for hard questions
- Cross-run passage dedup (same passage in test 3 and test 9)
- Teacher review workflow (API only — CLI/curl for now)
- Feedback flywheel (ratings → golden few-shot pool)
- Module 2 figures (placeholder only)
- PDF parser on 15 source tests (DNA extraction + real few-shot)
- MMR + multi-signal reranker (basic search only right now)
- IRT difficulty calibration
- Evaluation pipeline
- Production auth

---

## All Tasks

### Group A — Bug Fixes (do first, unblock everything)

**A1 · Fix LLM enum coercion**
Branch: `fix/llm-enum-coercion`
Files: `schemas/question.py`, `generation/validator.py`
What: Add `model_config = ConfigDict(use_enum_values=True)` to `LLMBatchOutput`.
Add `coerce_enum` wrapper to all enum fields in the LLM output schema.
Verify by re-running E2E — expect 85/85 questions generated.
Depends on: nothing
Effort: 1h

**A2 · Fix async test failures**
Branch: `fix/async-test-failures`
Files: `tests/unit/test_generate_test_cli.py`
What: Add `@pytest.mark.asyncio` to 3 failing tests.
Await `_resolve_blueprint()` call in each.
Verify: `pytest backend/tests/unit/` shows 497/497 passing.
Depends on: nothing
Effort: 30 min

**A3 · Fix intra-run passage dedup**
Branch: `fix/intra-run-passage-dedup`
Files: `generation/loop.py`
What: Track `used_passage_ids: set[str]` within a generation job.
Before assigning a passage to a slot, check it's not already used.
Pass `exclude_ids` to `search_passages()` so Qdrant filters them out.
Remove the modulo cycle fallback (it explicitly reuses passages).
Replace with: relax passage_type filter if no unused passage found.
Depends on: nothing
Effort: 1.5h


**A5 · Stabilize Qdrant Docker on Windows**
Branch: `fix/qdrant-docker-stability`
Files: `docker-compose.yml`
What: Add `restart: unless-stopped` to Qdrant service.
Add healthcheck with longer timeout and retries.
Add named volume with explicit path.
Add `QDRANT__STORAGE__PERFORMANCE__MAX_SEARCH_THREADS=2` env var
to reduce memory pressure on Windows Docker Desktop.
Depends on: nothing
Effort: 30 min

---

### Group B — Quality Fixes (do after Group A)

**B1 · Scope mismatch instruction for hard questions**
Branch: `quality/scope-mismatch-prompt`
Files: `generation/constants.py`, `generation/prompts.py`
What: In `build_user_prompt()`, when `slot_config.difficulty == Difficulty.HARD`:
inject scope mismatch instruction into TASK block:
"The question MUST ask about one scope (broad or narrow) while the
correct answer lives in a different scope. Trap choices should match
the question's apparent scope. The correct answer must still be
definitively supported by the passage."
Update SYSTEM_PROMPT: change "Hard questions may employ scope mismatch"
→ "Hard questions MUST employ scope mismatch."
Test: generate 5 hard questions, manually verify scope mismatch is present.
Depends on: A1 (want clean output to evaluate)
Effort: 1h

**B2 · Per-difficulty few-shot selection**
Branch: `quality/per-difficulty-few-shots`
Files: `generation/loop.py`, `generation/prompts.py`
What: Current system uses same fixed few-shot set for all slots.
Change: in `loop.py`, pass `slot.difficulty` to the few-shot retrieval call.
In `search_passages()` (or a new `search_few_shots()` function), filter
the question bank by difficulty before returning examples.
For hard slots: retrieve only examples flagged as `scope_mismatch=True`
(once that flag is added to the question bank schema).
Depends on: A1, B1
Effort: 2h

**B3 · Fix markdown fences in system prompt**
Branch: `quality/fix-prompt-json-example`
Files: `generation/constants.py`
What: Remove ` ```json ``` ` fences from the JSON example in SYSTEM_PROMPT.
Rule 4 says "No markdown fences" but the example uses them — contradicts itself.
Also: shuffle the example so correct answer is B or C, not always A.
Depends on: nothing
Effort: 15 min

**B4 · Per-slot difficulty distribution in TASK block**
Branch: `quality/slot-difficulty-distribution`
Files: `generation/prompts.py`
What: Current TASK block passes a single `difficulty_value` string.
Add computed breakdown:
```
easy_count = round(count * slot_config.difficulty_distribution.easy)
medium_count = round(count * slot_config.difficulty_distribution.medium)
hard_count = count - easy_count - medium_count
```
Inject: "Difficulty Distribution: {easy_count} easy, {medium_count} medium,
{hard_count} hard" into the TASK block.
Depends on: nothing
Effort: 30 min

**B5 · Cross-run passage dedup**
Branch: `quality/cross-run-passage-dedup`
Files: `storage/sqlite.py`, `storage/qdrant.py`, `generation/loop.py`
What: After each test is saved to inventory, record which passage_ids were used.
Before each generation run, query SQLite for passages used in last 10 tests.
Pass those IDs as `exclude_ids` to Qdrant search.
Add `last_used_at` and `use_count` updates to passage records after each run.
Depends on: A3
Effort: 2h

**B6 · Passage quality score in reranker**
Branch: `quality/passage-quality-reranker`
Files: `storage/qdrant.py`, `storage/sqlite.py`
What: Add `avg_question_quality: float` field to passage payload in Qdrant.
After teacher rates questions, update this score via feedback hook.
In `search_passages()`, add `w5 * passage_quality_score` to the ranking
(currently ranking is basic cosine — this makes it multi-signal).
Depends on: B5, feedback system (F1)
Effort: 2.5h

**B7 · Passage line coverage tracking**
Branch: `quality/passage-line-coverage`
Files: `generation/loop.py`, `generation/prompts.py`
What: Teacher flagged two problems at once: repetitive questions AND questions
clustering on the same line. Both solved by tracking which lines are already covered.
In `loop.py`: maintain `covered_lines: list[str]` per passage during a slot.
After each question is generated, append its `supporting_line` to the list.
In `build_user_prompt()`: inject into TASK block —
"Already covered lines — do NOT generate a question supported by any of these: {covered_lines}"
Also strengthens the existing "No repetition" rule by making it concrete, not advisory.
Depends on: A1
Effort: 1.5h

**B8 · Grammar quality + distractor justification in prompt**
Branch: `quality/grammar-quality-prompt`
Files: `generation/constants.py`, `generation/prompts.py`
What: Fixes two teacher complaints in one prompt change:

Fix 1 — Grammar mistakes in question stems and answer choices.
Add to SYSTEM_PROMPT rules section:
"6. **Grammar correctness** — Every question stem and every answer choice must be
grammatically correct standard English. Read each choice as a standalone sentence
before outputting. A grammatically broken question is always rejected regardless
of content quality."
Also add to WRITING_ADDON: "Writing module answer choices must be grammatically
valid sentences — the only intentional error is the one being tested."

Fix 2 — Two answer choices both arguable as correct (contradictions).
Root cause: Mistral picks a good_not_best choice without verifying it's
definitively ruled out by the passage.
Add to TASK block:
"For the good_not_best choice: you MUST explain in the reasoning field
exactly why it is definitively worse than the best_answer — cite the
specific passage evidence that rules it out. If you cannot articulate
a clear, passage-supported reason why it is inferior, choose a different
distractor. Two choices that can both be reasonably argued as correct is
a generation failure."
This forces Mistral to self-check before committing to a distractor.
The reasoning field becomes a justification gate, not just chain-of-thought.

Depends on: nothing
Effort: 30 min

---

### Group C — Missing Features (core pipeline)

**C1 · PDF parser on 15 source tests**
Branch: `feature/source-test-parser`
Files: `scraper/pdf_parser.py` (new), `scripts/parse_source_tests.py` (new)
What: Parse the 15 EST PDFs into structured data.
Extract: passages, questions, choices, correct answers (from separate AK files).
Output: `ParsedTest` objects saved to SQLite.
Store questions in Qdrant `question_bank` collection for few-shot retrieval.
This is the "real DNA" extraction — currently using hand-curated few-shots.
Known challenge: PDF column layout is complex (passage left, questions right).
Use `pdfplumber` — handles multi-column PDFs better than PyPDF2.
Manual tagging by teacher still required for: skill_type, difficulty per question.
Depends on: A1, A2
Effort: 8h (PDF parsing is hard)

**C2 · DNA extraction from parsed tests**
Branch: `feature/dna-extraction`
Files: `blueprint/extractor.py` (new), `scripts/extract_dna.py` (new)
What: Analyze the 15 parsed tests to validate/refine the hardcoded blueprint.
Compute actual distributions: questions per module, skills per module,
difficulty distribution, passage lengths, passage types.
Compare against DEFAULT_BLUEPRINT — flag discrepancies.
Update DEFAULT_BLUEPRINT to match real EST patterns.
Depends on: C1
Effort: 3h

**C3 · Module 2 figure support**
Branch: `feature/module2-figures`
Files: `scraper/figure_fetcher.py` (new), `schemas/passage.py`, `pdf/renderer.py`
What: Source scientific illustrations from Gutenberg HTML versions.
When scraping a book with illustrations, extract img tags and download images.
Store as `Figure(image_path, caption, alt_text, source_url)` on Passage.
In generation: pass `alt_text` to Mistral for figure question generation.
In PDF: embed actual image instead of placeholder.
Note: figures must be public domain illustrations (vintage natural history style).
Depends on: A3
Effort: 5h

**C4 · Writing passage editing target injection**
Branch: `feature/writing-editing-targets`
Files: `scraper/processor.py`, `schemas/passage.py`, `generation/prompts.py`
What: For writing passages, introduce deliberate editing targets.
Strategy: take clean Gutenberg passage → introduce surgical errors
(misplaced comma, weak transition, verbose sentence).
Store each error as `EditingTarget(sentence_index, issue_type, underline_start, underline_end)`.
Pass editing targets to Mistral in the TASK block so it generates
questions targeting specific underlined portions.
This makes Module 1 feel like real EST editing questions.
Depends on: B1, B4
Effort: 4h

**C5 · Teacher review workflow**
Branch: `feature/teacher-review-workflow`
Files: `api/routes/review.py` (new)
What: Currently tests go straight to inventory — no human gate.
Add review status to GeneratedTest: draft → reviewed → approved.
API endpoint: `PATCH /api/tests/{id}/review` with status + overall notes.
API endpoint: `GET /api/tests/{id}/questions` — list questions for review.
Teacher interacts via curl or any HTTP client (no UI).
Only approved tests are downloadable as PDFs.
Depends on: nothing
Effort: 2h

**C6 · MMR + multi-signal reranker**
Branch: `feature/mmr-reranker`
Files: `storage/qdrant.py`
What: Current search is basic cosine similarity — flat.
Implement MMR (Maximal Marginal Relevance) for intra-test diversity:
each passage selection penalizes future selections in similar topic space.
Implement multi-signal scorer:
```
score = w1 * semantic_similarity
      + w2 * reading_level_match
      + w3 * topic_novelty_score
      + w4 * recency_penalty
      + w5 * passage_quality_score
```
Expose weights as config so they can be tuned.
Depends on: A3, B5, B6
Effort: 4h

---

### Group D — Feedback & Quality Loop

**F1 · Feedback capture API**
Branch: `feature/feedback-api`
Files: `api/routes/feedback.py` (exists, needs implementation), `storage/sqlite.py`
What: POST /api/tests/{test_id}/questions/{question_id}/feedback
Body: `{rating: 1-5, flags: list[str], notes: str}`
GET /api/tests/{test_id}/feedback → list of feedback records
Save to SQLite `question_feedback` table.
Note: this is the FRIEND'S TASK — scaffold is already done.
Depends on: A2
Effort: 2-4h (friend)

**F2 · Golden few-shot pool from feedback**
Branch: `feature/golden-few-shot-pool`
Files: `storage/qdrant.py`, `storage/sqlite.py`, `generation/loop.py`
What: Questions rated ≥ 4 with flag = excellent get promoted.
Add `is_golden: bool` field to question_bank Qdrant collection.
After teacher rates a question excellent: upsert it to question_bank with `is_golden=True`.
In few-shot retrieval: prefer golden examples over raw source-test examples.
Over time: teacher's best generated questions become the style anchor.
Depends on: F1, C1
Effort: 3h


---

### Group E — ML/BERT Components (post-MVP)

**E1 · RoBERTa answer correctness validator**
Branch: `feature/roberta-validator`
Files: `generation/validator.py`
What: Add RoBERTa QA model (fine-tuned on SQuAD or RACE) as extra validation gate.
For each generated question: feed passage + question → model predicts answer.
If model prediction doesn't match `correct_answer` → flag for retry.
Use `deepset/roberta-base-squad2` from HuggingFace (free, runs locally).
This is the post-MVP answer correctness layer — MVP uses substring check only.
Depends on: A1
Effort: 4h

**E2 · Semantic deduplication**
Branch: `feature/semantic-dedup`
Files: `generation/validator.py`, `storage/qdrant.py`
What: After generating a question, embed it with `all-MiniLM-L6-v2`.
Search question_bank for cosine similarity > 0.85.
If near-duplicate found: reject question, trigger retry with instruction
to generate something meaningfully different.
Depends on: A1, C1
Effort: 3h

**E3 · IRT difficulty calibration**
Branch: `feature/irt-difficulty`
Files: `generation/validator.py`, `schemas/question.py`
What: Item Response Theory — assign continuous difficulty parameter θ
instead of easy/medium/hard labels.
Use `py-irt` library with question bank from source tests as calibration set.
Map θ to difficulty bins for blueprint compliance checks.
This is how real EST calibrates difficulty — post-MVP only.
Depends on: C1, C2
Effort: 6h

**E4 · Evaluation pipeline**
Branch: `feature/evaluation-pipeline`
Files: `scripts/run_eval.py` (new), `scripts/eval_report.py` (new)
What: Hold out 3-4 of 15 source tests as eval set (never used in few-shots).
Run generated test against eval metrics:
- Teacher rating distribution (from feedback)
- Answerability (RoBERTa correctness rate)
- Style similarity (BERTScore vs real EST questions)
- Difficulty distribution accuracy
- Skill distribution accuracy
Run after every prompt change. Print before/after comparison.
Depends on: C1, E1, F1
Effort: 5h

---

### Group P — Production (scale-up)

**P1 · Production auth**
Branch: `feature/auth`
Files: `api/middleware/auth.py` (new)
What: API key auth per teacher (no OAuth needed for small scale).
Middleware checks `X-API-Key` header against SQLite `api_keys` table.
Depends on: nothing
Effort: 2h

**P2 · LLM fallback model**
Branch: `feature/llm-fallback`
Files: `generation/caller.py`
What: If Mistral returns 503 or rate limit exceeded:
fall back to `open-mistral-7b` (cheaper, faster).
If that fails: raise `GenerationFailedError` with clear message.
Depends on: A1
Effort: 1.5h

**P3 · Migrate SQLite → PostgreSQL**
Branch: `feature/postgres-migration`
Files: `storage/db.py`, `storage/*.py`
What: Replace `aiosqlite` with `asyncpg` + `sqlalchemy async`.
Migration script for existing data.
Update `docker-compose.yml` to add PostgreSQL service.
Depends on: P1
Effort: 6h

**P4 · Telemetry + structured logging**
Branch: `feature/telemetry`
Files: `main.py`, all modules
What: `structlog` is in the stack but not aggregated.
Add: request ID correlation, generation job metrics,
per-slot timing, failure rate tracking.
Export to: simple JSON log files (no external service needed for small scale).
Depends on: nothing
Effort: 3h

---

## Task Dependency Matrix

```
A1 ──────────────────────────────────► B1 ──► B2
A1 ──────────────────────────────────► E1
A1 ──────────────────────────────────► E2
A1 ──────────────────────────────────► P2
A1, A2 ──────────────────────────────► C1 ──► C2 ──► E3
                                        C1 ──► F2
                                        C1 ──► E2
                                        C1 ──► E4
A3 ──────────────────────────────────► B5 ──► B6
A3 ──────────────────────────────────► C3
A3 ──────────────────────────────────► C6 (partial)
A2 ──────────────────────────────────► F1
B1 ──────────────────────────────────► B2
B1, B4 ──────────────────────────────► C4
B5, B6, A3 ──────────────────────────► C6
F1 ──────────────────────────────────► F2
F1, C1 ──────────────────────────────► F2
C1, E1, F1 ──────────────────────────► E4

B3, B4, B8 ──────────────────────────► (no deps, standalone)
A1 ──────────────────────────────────► B7
A5 ──────────────────────────────────► (no deps, standalone)
P4 ──────────────────────────────────► (no deps, run anytime)

Note: E1 (RoBERTa) promoted from Sprint 4 → Sprint 2 (teacher flagged answer contradictions)
```

---

## Build Order (recommended)

### Sprint 1 — Stabilize (this week)
Goal: clean pipeline, 85/85 questions, CI green

| Task | Branch | Owner | Effort |
|---|---|---|---|
| A1 fix enum coercion | `fix/llm-enum-coercion` | Gemy | 1h |
| A2 fix async tests | `fix/async-test-failures` | Gemy | 30m |
| A3 fix intra-run dedup | `fix/intra-run-passage-dedup` | Gemy | 1.5h |
| A5 stabilize Qdrant | `fix/qdrant-docker-stability` | Gemy | 30m |
| B3 fix prompt fences | `quality/fix-prompt-json-example` | Gemy | 15m |
| B4 slot difficulty dist | `quality/slot-difficulty-distribution` | Gemy | 30m |
| B7 line coverage tracking | `quality/passage-line-coverage` | Gemy | 1.5h |
| B8 grammar prompt fix | `quality/grammar-quality-prompt` | Gemy | 15m |
| F1 feedback API | `feature/feedback-api` | Friend | 3h |

**Sprint 1 exit criteria:**
- `pytest backend/tests/unit/` → 497/497 green
- E2E run → 85/85 questions generated
- No two questions reference the same supporting line
- POST /api/tests/{id}/questions/{qid}/feedback works

---

### Sprint 2 — Quality (next week)
Goal: questions feel like real EST, no contradictions, no passage reuse, review API done

| Task | Branch | Owner | Effort |
|---|---|---|---|
| B1 scope mismatch | `quality/scope-mismatch-prompt` | Gemy | 1h |
| B2 per-difficulty few-shots | `quality/per-difficulty-few-shots` | Gemy | 2h |
| B5 cross-run dedup | `quality/cross-run-passage-dedup` | Gemy | 2h |
| C5 teacher review workflow | `feature/teacher-review-workflow` | Gemy | 2h |
| E1 RoBERTa validator ⬆️ promoted | `feature/roberta-validator` | Gemy | 4h |

**Sprint 2 exit criteria:**
- Hard questions demonstrably use scope mismatch
- No passage repeated within a test or across last 10 tests
- Teacher can review, rate, and approve a test via API (curl)
- Answer contradictions caught by RoBERTa before test is assembled

---

### Sprint 3 — Real Data (when PDFs arrive)
Goal: actual EST DNA, real few-shots, Module 2 figures

| Task | Branch | Owner | Effort |
|---|---|---|---|
| C1 PDF parser | `feature/source-test-parser` | Gemy | 8h |
| C2 DNA extraction | `feature/dna-extraction` | Gemy | 3h |
| C3 Module 2 figures | `feature/module2-figures` | Gemy | 5h |
| C4 writing editing targets | `feature/writing-editing-targets` | Gemy | 4h |
| F2 golden few-shot pool | `feature/golden-few-shot-pool` | Gemy | 3h |

**Sprint 3 exit criteria:**
- Blueprint validated against real test DNA
- Real EST questions used as few-shots (not hand-curated)
- Module 2 PDFs include actual scientific illustrations
- Writing passages have tagged editing targets

---

### Sprint 4 — Intelligence (post-MVP ML)
Goal: answer verification, dedup, difficulty calibration, evaluation

| Task | Branch | Owner | Effort |
|---|---|---|---|
| C6 MMR reranker | `feature/mmr-reranker` | Gemy | 4h |
| B6 passage quality reranker | `quality/passage-quality-reranker` | Gemy | 2.5h |
| E2 semantic dedup | `feature/semantic-dedup` | Gemy | 3h |
| E3 IRT difficulty | `feature/irt-difficulty` | Gemy | 6h |
| E4 eval pipeline | `feature/evaluation-pipeline` | Gemy | 5h |

**Sprint 4 exit criteria:**
- Duplicate questions detected and rejected
- Difficulty scores are continuous (IRT θ), not just 3 labels
- Eval pipeline runs in CI after every prompt change

---

### Sprint 5 — Production
Goal: multi-teacher, auth, scale

| Task | Branch | Owner | Effort |
|---|---|---|---|
| P1 auth | `feature/auth` | Gemy | 2h |
| P2 LLM fallback | `feature/llm-fallback` | Gemy | 1.5h |
| P3 Postgres migration | `feature/postgres-migration` | Gemy | 6h |
| P4 telemetry | `feature/telemetry` | Gemy | 3h |

---

## Branch Naming Convention

```
fix/     — bug fixes (A group)
quality/ — prompt and generation quality improvements (B group)
feature/ — new capabilities (C, F, E, P groups)
```

All branches cut from `main`. PR into `main` after each task.
No long-lived feature branches — merge frequently.

---

## What to give the friend

**Sprint 1:** F1 — feedback API endpoints (backend/app/api/routes/feedback.py)

One task. Isolated, well-defined, clear deliverable.
See the friend task brief in the full_plan.md for copy-paste instructions.

---

## Effort Summary

| Sprint | Gemy | Friend | Total |
|---|---|---|---|
| 1 — Stabilize | 5.75h | 3h | 8.75h |
| 2 — Quality | 11h | — | 11h |
| 3 — Real Data | 23h | — | 23h |
| 4 — Intelligence | 20.5h | — | 20.5h |
| 5 — Production | 12.5h | — | 12.5h |
| **Total** | **72.75h** | **3h** | **75.75h** |

At side-project pace (4-6h/week): ~3-4 months to full system.
At active pace (15-20h/week): ~5-6 weeks.

Sprint 1 can be done in one focused afternoon session.
