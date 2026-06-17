# EST Synthesizer

A full-stack pipeline that scrapes source passages, generates Educational Skills Test (EST) questions via LLM, and exports print-ready PDFs.

## Architecture

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

**Stack**: Python 3.11+ / FastAPI / Pydantic / SQLite (aiosqlite) / Qdrant / LiteLLM / WeasyPrint

## Project Structure

```
est-synthesizer/
├── backend/
│   └── app/
│       ├── config.py              # Settings (pydantic-settings, .env)
│       ├── main.py                # FastAPI app + lifespan
│       ├── schemas/               # Pydantic models & enums
│       │   ├── enums.py           # 8 enums (PassageType, SkillType, Difficulty, etc.)
│       │   ├── question.py        # AnswerChoice, GeneratedQuestion
│       │   ├── passage.py         # Passage
│       │   ├── test.py            # TestBlueprint, ModuleConfig, GeneratedTest
│       │   ├── job.py             # GenerationJob
│       │   ├── feedback.py        # QuestionFeedback
│       │   └── llm.py             # LLMConfig, LiteLLMRequest
│       ├── storage/               # Data persistence
│       │   ├── db.py              # SQLite connection + schema init
│       │   ├── jobs.py            # Job CRUD
│       │   ├── tests.py           # Test inventory CRUD
│       │   ├── feedback.py        # Feedback CRUD
│       │   ├── blueprints.py      # Blueprint CRUD + seeding
│       │   └── qdrant.py          # Async Qdrant manager (embedding + MMR search)
│       ├── blueprint/
│       │   └── default.py         # DEFAULT_BLUEPRINT + HARDER_BLUEPRINT (85 Q each)
│       ├── routes/
│       │   └── blueprints.py      # 6 REST endpoints for blueprint management
│       ├── static/
│       │   └── blueprint-editor.html  # Single-page blueprint editor UI
│       ├── generation/            # LLM pipeline (stub)
│       ├── scraper/               # Passage scraper (stub)
│       └── pdf/                   # PDF renderer (stub)
│       └── tests/                 # Test suite
│           ├── conftest.py         # Shared fixtures
│           ├── unit/               # Pure unit tests (schemas, config, blueprint)
│           └── integration/        # Storage + route integration tests
├── run.py                         # Uvicorn entry point
├── docker-compose.yml             # Qdrant service
├── pyproject.toml                 # Project config + deps
├── .env.example                   # Reference env vars
└── full_plan.md                   # Original build plan
```

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for Qdrant vector DB)

### Setup

```bash
# Install dependencies
uv sync

# Copy env template and set your Mistral API key
cp .env.example .env
# Edit .env — set MISTRAL_API_KEY

# Start Qdrant (required for embedding/search features)
docker compose up -d
```

### Run the Server

```bash
uv run python run.py
```

The server starts on `http://127.0.0.1:8000` by default (configurable via `.env`).

### Run Tests

```bash
# All tests (298 tests)
uv run pytest

# Unit tests only
uv run pytest backend/tests/unit/

# Integration tests only
uv run pytest backend/tests/integration/

# Verbose output
uv run pytest -v

# Specific module
uv run pytest backend/tests/unit/test_schemas_question.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/config` | Server config (host, port) |
| GET | `/health` | Health check |
| GET | `/api/blueprints` | List all blueprints |
| GET | `/api/blueprints/{id}` | Get a blueprint |
| POST | `/api/blueprints` | Create custom blueprint |
| PUT | `/api/blueprints/{id}` | Update custom blueprint |
| DELETE | `/api/blueprints/{id}` | Delete custom blueprint |
| POST | `/api/blueprints/{id}/duplicate` | Duplicate a blueprint |

## Blueprint Editor

Open `http://localhost:8000/ui/` in your browser for the single-page blueprint editor. Built-in blueprints (DEFAULT, HARDER) are read-only — duplicate them to customize.

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `HOST` | `127.0.0.1` | No | Server bind address |
| `PORT` | `8000` | No | Server bind port |
| `MISTRAL_API_KEY` | — | **Yes** | Mistral API key for LLM calls |
| `MISTRAL_RATE_LIMIT` | `1.0` | No | Rate limit (req/s) |
| `QDRANT_URL` | `http://localhost:6333` | No | Qdrant server URL |
| `QDRANT_COLLECTION_LONG` | `long_passages` | No | Long passages collection |
| `QDRANT_COLLECTION_SHORT` | `short_passages` | No | Short passages collection |
| `EMBEDDING_MODEL` | `mistral/mistral-embed` | No | Embedding model (via LiteLLM) |
| `EMBEDDING_VECTOR_SIZE` | `1024` | No | Embedding vector dimensions |
| `SQLITE_PATH` | `data/db/est.db` | No | SQLite database path |
| `GENERATED_PDF_PATH` | `data/generated/` | No | PDF output directory |

## Test Blueprint Structure

Each blueprint defines 3 modules totaling 85 questions:

| Module | Type | Questions | Notes |
|--------|------|-----------|-------|
| 1 | Writing | 35 | Wordy answer style |
| 2 | Reading Long | 25 | Has figure |
| 3 | Reading Short | 25 | Alternating passages |

Two built-in blueprints are seeded on first startup:
- **DEFAULT_BLUEPRINT** — 20% easy / 40% medium / 40% hard
- **HARDER_BLUEPRINT** — 10% easy / 35% medium / 55% hard

## Status

| Component | Status |
|-----------|--------|
| Schemas | Done |
| SQLite Storage | Done |
| Blueprint Config + UI | Done |
| Qdrant Vector Store | Done |
| Test Suite (298 tests) | Done |
| Passage Scraper | Stub |
| LLM Generation Pipeline | Stub |
| PDF Renderer | Stub |
