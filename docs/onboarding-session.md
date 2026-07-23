# Onboarding Session: EST Synthesizer

## Session Overview 

**Duration**: 90 minutes
**Goal**: Understand the architecture, run the pipeline end-to-end, and make your first code change
**Prerequisites**: Python 3.11+, uv, Docker Desktop, Node.js 18+

---

## Part 1: Project Context (15 min)

### What is EST?

EST (Egyptian Scholastic Test) is Egypt's standardized college entrance exam — comparable to the SAT in structure. The test has:
- **Module 1**: Writing/editing (35 questions) — wordy answer choices, grammar/punctuation focus
- **Module 2**: Reading long passages with figures (25 questions)
- **Module 3**: Reading short passages (25 questions)

**Total**: 85 questions per test, ~3 hours

### What are we building?

An automated pipeline that:
1. **Scrapes** public-domain passages from Project Gutenberg
2. **Embeds** them in Qdrant (vector DB) for semantic search
3. **Generates** EST-style questions via LLM (Mistral)
4. **Assembles** questions into a structured test
5. **Renders** print-ready PDFs (student + teacher versions)

### Why does this matter?

Manual test creation is slow and inconsistent. This pipeline ensures:
- Questions are grounded in real passages (no fabrication)
- Consistent difficulty distribution
- Scalable — generate 10 tests in the time it takes to make 1 manually

---

## Part 2: Architecture Deep-Dive (20 min)

### Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐
│   Scraper    │────▶│   Qdrant     │────▶│   Generation │────▶│  PDF      │
│  (Gutenberg) │     │  Vector DB   │     │   Pipeline   │     │  Renderer │
└─────────────┘     └──────────────┘     └──────────────┘     └───────────┘
                            │                     │
                            │                     │
                     ┌──────▼──────┐        ┌─────▼─────┐
                     │  FastAPI    │        │   SQLite   │
                     │  REST + UI  │        │   Storage  │
                     └─────────────┘        └─────────────┘
```

### Key Components

**1. Scraper** (`backend/app/scraper/`)
- Fetches books from Gutendex API
- Strips Gutenberg boilerplate
- Chunks text into passages (~300 words)
- Classifies as long/short, essay/narrative/scientific/etc.
- Upserts into Qdrant with embeddings

**2. Qdrant** (vector DB)
- Collections: `long_passages`, `short_passages`
- Stores: passage text, metadata, BGE embeddings (1024 dims)
- Search: semantic similarity + MMR for diversity

**3. Generation Pipeline** (`backend/app/generation/`)
The heart of the system:

```
run_generation_loop()
├── _retrieve_passages()      # Parallel Qdrant search per module type
├── for each slot:
│   ├── _generate_slot()      # Sequential, with retries
│   │   ├── build_system_prompt()   # Static rules
│   │   ├── build_user_prompt()     # Passage + task + few-shots
│   │   ├── get_queue().submit()    # LLM call via LiteLLM
│   │   ├── LLMBatchOutput(**raw)   # Parse JSON
│   │   └── validate_question()     # Groundedness + structure
│   └── update_job_status()    # Progress tracking
├── assemble_test()           # Group by passage → GeneratedTest
├── render_student_pdf()      # Jinja2 + WeasyPrint
├── render_teacher_pdf()      # With answer key
└── save_test()               # SQLite inventory
```

**4. Schemas** (`backend/app/schemas/`)
- 8 enums (LowerStrEnum — `auto()` = lower-cased name)
- `Passage`: id, text, type, category, word_count, reading_level
- `ModuleSlot`: skill_type, difficulty, question_count
- `LLMQuestionOutput`: what the LLM returns per question
- `GeneratedQuestion`: enriched with system-assigned fields

**5. Storage** (`backend/app/storage/`)
- **SQLite** (aiosqlite): jobs, tests, feedback, blueprints
- **Qdrant**: passage embeddings + metadata

---

## Part 3: Live Demo — Run the Pipeline (25 min)

### Step 1: Start infrastructure

```bash
# Qdrant + LiteLLM proxy
docker compose up -d

# Verify Qdrant is healthy
curl http://localhost:6333/health
```

### Step 2: Bootstrap passages

```bash
# Dry run first (no Qdrant writes)
uv run python scripts/bootstrap_library.py --max-books 5 --dry-run

# Real run
uv run python scripts/bootstrap_library.py --max-books 50 --topics "science,history"
```

Expected output:
```
Total books processed : 50
Total passages        : 324
Breakdown by type:
  long                 210
  short                114
```

### Step 3: Inspect Qdrant

```bash
uv run python scripts/qdrant_tool.py collections
uv run python scripts/qdrant_tool.py search "scientific experiment" --limit 3
```

### Step 4: Generate a test

```bash
# Start backend
uv run python run.py

# In another terminal — generate test
uv run python scripts/test_real_call.py
```

Expected: ~3-5 minutes, generates 85 questions, renders PDFs to `data/generated/`

### Step 5: Verify the output

```bash
# Check SQLite inventory
uv run python -c "import asyncio; from backend.app.storage.tests import list_tests; print(asyncio.run(list_tests()))"

# Open PDF
start data/generated/test_<id>_student.pdf
```

---

## Part 4: Code Walkthrough (20 min)

### The Generation Loop (`generation/loop.py`)

Open this file and trace through:

1. **`run_generation_loop()`** — entry point
   - Creates QdrantManager
   - Calls `_retrieve_passages()` once (parallel fetch)
   - Iterates modules → slots sequentially
   - Tracks `used_passage_ids`, `covered_lines`, `per_passage_count`

2. **`_retrieve_passages()`** — parallel Qdrant search
   - Groups slots by module type (WRITING, READING_LONG, READING_SHORT)
   - Fetches each group in parallel with `asyncio.gather()`
   - Falls back to relaxed filter if not enough passages

3. **`_generate_slot()`** — single slot with retries
   - Builds system + user prompt
   - Submits to LLM queue
   - Validates each question
   - Retries up to 3 times on failure

### The Prompt Builder (`generation/prompts.py`)

Open `build_user_prompt()` and identify:
- `<PASSAGE>` block — source text
- `<UNDERLINED_PORTIONS>` — writing module targets
- `<FEW_SHOT_EXAMPLES>` — in-context examples
- `<TASK>` — skill, difficulty, count, constraints
- `<CURRENT_STATE>` — progress tracking

### The Schemas (`schemas/question.py`)

Key insight: **two-layer validation**
1. **Pydantic schema** (`LLMQuestionOutput`) — structure, enums, types
2. **Custom validators** (`coerce_skill_type`, `coerce_difficulty`) — handle LLM inventiveness
3. **Post-validation** (`validate_question()`) — groundedness, substring check

---

## Part 5: Your First Change (10 min)

### Exercise: Add a new skill type

**Goal**: Add `COMPARISON` to the `SkillType` enum and use it in a test.

**Steps**:

1. **Add enum member** (`schemas/enums.py`)
   ```python
   class SkillType(LowerStrEnum):
       # ... existing ...
       COMPARISON = auto()  # "comparison"
   ```

2. **Add description** (`generation/constants.py`)
   ```python
   SKILL_TYPE_DESCRIPTIONS = {
       # ... existing ...
       "comparison": "Comparison — analyzing similarities and differences between ideas or texts",
   }
   ```

3. **Update DEFAULT_BLUEPRINT** (`blueprint/default.py`)
   - Add a slot with `skill_type=SkillType.COMPARISON`

4. **Run tests**
   ```bash
   uv run pytest backend/tests/unit/test_schemas_enums.py -v
   ```

5. **Generate a test with the new blueprint**
   ```bash
   uv run python scripts/test_real_call.py
   ```

---

## Part 6: Debugging Workflow (10 min)

### Common Issues

**1. Tests fail with "ModuleNotFoundError"**
```bash
uv sync  # reinstall dependencies
```

**2. Qdrant connection refused**
```bash
docker compose up -d
docker compose ps  # verify health
```

**3. LLM rate limit**
```bash
# Lower rate limit in .env
MISTRAL_RATE_LIMIT=0.5
```

**4. Zero questions generated**
- Check Qdrant has passages: `uv run python scripts/qdrant_tool.py stats`
- Check LLM API key: `echo $env:MISTRAL_API_KEY`
- Check logs: `data/logs/est-synthesizer.log`

### Debugging Tools

```bash
# Run with debug logging
$env:LOG_LEVEL="DEBUG"
uv run python run.py

# Inspect a specific job
uv run python -c "
import asyncio
from backend.app.storage.jobs import get_job
job = asyncio.run(get_job('your-job-id'))
print(job)
"

# Search Qdrant manually
uv run python scripts/qdrant_tool.py search "quantum physics" --limit 5 --collection long_passages
```

---

## Part 7: Next Steps

### Your First Week

1. **Day 1**: Run the full pipeline, read `full_dev_plan.md`
2. **Day 2**: Pick a **Group A** bug fix (A1, A2, A3, A5)
3. **Day 3**: Pick a **Group B** quality fix (B3, B4, B7, B8)
4. **Day 4-5**: Tackle **F1** (feedback API) or **C5** (teacher review)

### Resources

- `full_dev_plan.md` — roadmap with effort estimates
- `docs/api.md` — endpoint reference
- `README.md` — quick start
- `CONTRIBUTING.md` — conventions + workflow

### Getting Help

- Check logs first: `data/logs/est-synthesizer.log`
- Run tests: `uv run pytest -v`
- Ask in team chat with: error message, logs, steps to reproduce

---

## Cheat Sheet

```bash
# Setup
uv sync
copy .env.example .env
docker compose up -d

# Tests
uv run pytest
uv run pytest backend/tests/unit/
uv run pytest -k test_name -v

# Run
uv run python run.py                    # backend
cd frontend && npm run dev              # frontend

# Scripts
uv run python scripts/test_real_call.py
uv run python scripts/bootstrap_library.py --max-books 50
uv run python scripts/qdrant_tool.py stats
```
