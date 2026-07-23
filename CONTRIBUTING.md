# Contributing to EST Synthesizer

## Quick Start

```bash
# 1. Clone and enter
git clone <repo-url>
cd est-synthesizer

# 2. Install dependencies
uv sync

# 3. Copy environment file
copy .env.example .env
# Edit .env and set MISTRAL_API_KEY

# 4. Start Qdrant (vector DB)
docker compose up -d

# 5. Run tests
uv run pytest

# 6. Start backend (http://127.0.0.1:8000)
uv run python run.py

# 7. Start frontend (http://localhost:3000) — in another terminal
cd frontend
npm install
npm run dev
```

## Code Conventions

- **Python 3.11+**, type hints everywhere
- **Pydantic v2** for schemas (`ConfigDict(strict=True)` for LLM-facing models)
- **structlog** for logging — never `print()`
- **Async all the way**: FastAPI, aiosqlite, Qdrant async client
- **LowerStrEnum** for all enums — `auto()` produces lower-cased names
- **Docstrings** on every public function/class

## Project Structure

```
backend/app/
├── main.py                 # FastAPI app + lifespan
├── config.py               # pydantic-settings
├── logging_config.py       # structlog setup
├── schemas/                # Pydantic models + enums
│   ├── enums.py            # 8 enums (LowerStrEnum base)
│   ├── question.py         # AnswerChoice, GeneratedQuestion, LLMBatchOutput
│   ├── passage.py          # Passage, Figure
│   ├── test.py             # TestBlueprint, ModuleSlot, GeneratedTest
│   ├── job.py              # GenerationJob
│   ├── feedback.py         # QuestionFeedback
│   └── llm.py              # LLMConfig, LiteLLMRequest
├── storage/                # Data persistence
│   ├── db.py               # SQLite connection + schema init
│   ├── jobs.py             # Job CRUD
│   ├── tests.py            # Test inventory CRUD
│   ├── feedback.py         # Feedback CRUD
│   ├── blueprints.py       # Blueprint CRUD + seeding
│   └── qdrant.py           # Async Qdrant manager (embedding + MMR search)
├── blueprint/
│   └── default.py          # DEFAULT_BLUEPRINT + HARDER_BLUEPRINT
├── routes/                 # REST routers
│   ├── blueprints.py       # 6 endpoints
│   └── scraper.py          # 3 endpoints
├── api/                    # API routers
│   ├── generate.py         # POST /api/tests/generate
│   ├── progress.py         # SSE /api/tests/{id}/progress
│   └── feedback.py         # POST/GET feedback
├── generation/             # LLM pipeline
│   ├── loop.py             # Sequential slot generation with retries
│   ├── caller.py           # LLMQueue with rate limiting
│   ├── prompts.py          # build_system_prompt, build_user_prompt
│   ├── validator.py        # Post-LLM validation
│   ├── assembler.py        # Assemble questions → GeneratedTest
│   └── few_shot.py         # Curated in-context examples
├── scraper/                # Gutenberg pipeline
│   ├── gutenberg.py        # Gutendex API client
│   ├── processor.py        # chunk_text, process_raw_text
│   └── constants.py        # Prompt constants
├── pdf/
│   └── renderer.py         # Jinja2 + WeasyPrint
└── tests/                  # pytest suite
    ├── conftest.py
    ├── unit/
    └── integration/
```

## Running Tests

```bash
# All tests (597 tests)
uv run pytest

# Unit tests only
uv run pytest backend/tests/unit/

# Integration tests only
uv run pytest backend/tests/integration/

# Verbose
uv run pytest -v

# Specific file
uv run pytest backend/tests/unit/test_schemas_question.py
```

## Branching & PRs

- Branch from `main`: `fix/`, `quality/`, `feature/`
- One logical change per branch
- PR must pass all tests
- No force-push to shared branches

## Common Tasks

### Generate a test end-to-end

```bash
# Start services first: Qdrant + backend
uv run python scripts/test_real_call.py
```

### Bootstrap passage library

```bash
uv run python scripts/bootstrap_library.py --max-books 50 --topics "science,history"
```

### Inspect Qdrant

```bash
uv run python scripts/qdrant_tool.py collections
uv run python scripts/qdrant_tool.py search "scientific experiment" --limit 5
```

## Environment Variables

Key vars in `.env` — see `config.py` for full list:

| Variable | Required | Default |
|---|---|---|
| `MISTRAL_API_KEY` | **Yes** | — |
| `MISTRAL_RATE_LIMIT` | No | `1.0` |
| `QDRANT_URL` | No | `http://localhost:6333` |
| `EMBEDDING_MODEL` | No | `BAAI/bge-large-en-v1.5` |
| `SQLITE_PATH` | No | `data/db/est.db` |
| `GENERATED_PDF_PATH` | No | `data/generated/` |
| `LOG_LEVEL` | No | `INFO` |
| `LOG_FORMAT` | No | `console` |

## Troubleshooting

- **Qdrant connection refused**: `docker compose up -d` and wait for healthcheck
- **Tests hang**: check Qdrant is running; integration tests need it
- **LLM rate limit**: lower `MISTRAL_RATE_LIMIT` or use LiteLLM proxy
- **Import errors**: run `uv sync` after pulling new deps
