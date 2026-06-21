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
│       │   ├── blueprints.py      # 6 REST endpoints for blueprint management
│       │   └── scraper.py         # 3 scraper API endpoints
│       ├── static/
│       │   └── blueprint-editor.html  # Single-page blueprint editor UI
│       ├── generation/            # LLM pipeline (stub)
│       ├── logging_config.py      # structlog production logging configuration
│       ├── scraper/               # Passage scraper (Gutendex API + processing)
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
# All tests (507 tests)
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
| GET | `/api/scraper/catalogue` | Fetch Gutendex catalogue (query: `topics`, `max_books`) |
| GET | `/api/scraper/book/{book_id}` | Download + chunk + process a single book |
| GET | `/api/scraper/pipeline` | Full pipeline: catalogue → download → process (query: `max_books`, `topics`) |

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
| `LOG_LEVEL` | `INFO` | No | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | `console` | No | Log format: `console` (colored) or `json` (structured) |
| `GUTENDEX_BASE_URL` | `https://gutendex.com/books` | No | Gutendex API base URL |
| `GUTENDEX_MAX_BOOKS` | `200` | No | Max books per catalogue fetch |
| `GUTENDEX_REQUEST_TIMEOUT` | `15.0` | No | Catalogue request timeout (seconds) |
| `GUTENDEX_PASSAGE_TIMEOUT` | `30.0` | No | Per-book download timeout (seconds) |
| `GUTENDEX_MIN_AUTHOR_BIRTH_YEAR` | `1700` | No | Reject books with all authors born before this year |

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

## Scraper Pipeline

The scraper pipeline fetches public-domain books from Project Gutenberg via the [Gutendex](https://gutendex.com/) API, extracts passage-sized chunks, classifies them, and produces validated `Passage` objects.

### Workflow

```
Gutendex API ──► fetch_catalogue() ──► filtered book list
                                              │
                                              ▼
                              fetch_passage_text() ──► raw Gutenberg text
                                              │
                                              ▼
                                  strip_gutenberg_boilerplate()
                                              │
                                              ▼
                                     chunk_text() ──► sentence-aligned chunks
                                              │
                                              ▼
                                  process_raw_text() ──► Passage objects
```

### API Commands (manual testing)

Start the server:
```bash
uv run python run.py
```

Then in another terminal:

```bash
# Fetch catalogue (first 10 books matching "science")
curl "http://localhost:8000/api/scraper/catalogue?max_books=10"

# Download and process a specific book by Gutendex ID (e.g. 84 = Frankenstein)
curl "http://localhost:8000/api/scraper/book/84"

# Full pipeline: fetch catalogue → download first 3 books → process all passages
curl "http://localhost:8000/api/scraper/pipeline?max_books=3&topics=science,history"
```

All activity is logged via structlog to the console and to `data/logs/est-synthesizer.log`.

### Using the Scraper Programmatically

```python
import asyncio
from backend.app.scraper import fetch_catalogue, fetch_passage_text
from backend.app.scraper.processor import chunk_text, process_raw_text

async def scrape():
    books = await fetch_catalogue(topics=["science"], n=5)
    for book in books:
        text = await fetch_passage_text(book["id"])
        chunks = chunk_text(text, target_words=300)
        for chunk in chunks:
            passage = process_raw_text(
                chunk,
                source_url=book["formats"]["text/plain"],
                source_title=book["title"],
            )
            print(f"  -> {passage.id} ({passage.passage_type.value}, {passage.word_count} words)")

asyncio.run(scrape())
```

### Logging

All scraper modules use **structlog** with structured keyword arguments. Set `LOG_FORMAT=json` in `.env` for JSON log output suitable for log aggregators (ELK, Datadog, etc.).

## Status

| Component | Status |
|-----------|--------|
| Schemas | Done |
| SQLite Storage | Done |
| Blueprint Config + UI | Done |
| Qdrant Vector Store | Done |
| Test Suite (507 tests) | Done |
| Passage Scraper | Done |
| LLM Generation Pipeline | Stub |
| PDF Renderer | Stub |
