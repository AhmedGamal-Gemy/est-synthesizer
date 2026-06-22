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
│       ├── generation/            # LLM pipeline (T11 loop + T12 assembler, PR #13)
│       ├── logging_config.py      # structlog production logging configuration
│       ├── scraper/               # Passage scraper (Gutendex API + processing)
│       └── pdf/                   # PDF renderer (Jinja2 + WeasyPrint, T14)
│       └── tests/                 # Test suite
│           ├── conftest.py         # Shared fixtures
│           ├── unit/               # Pure unit tests (schemas, config, blueprint)
│           └── integration/        # Storage + route integration tests
├── frontend/                      # Vite + React + Tailwind UI
│   ├── src/
│   │   ├── App.jsx                # Main app component
│   │   ├── api/                   # Backend API client (axios)
│   │   ├── components/            # UI components
│   │   └── main.jsx               # Entry point
│   ├── index.html
│   ├── vite.config.js             # Dev server on :3000, proxies /api → :8080
│   ├── tailwind.config.js
│   └── package.json
├── scripts/                       # CLI scripts
│   ├── bootstrap_library.py       # Bootstrap passage library from Gutenberg
│   ├── qdrant_tool.py             # Qdrant CRUD and visualization tool
│   └── bootstrap/
│       └── stats.py               # Stats tracker for bootstrap runs
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
- Node.js 18+ (for frontend)
- npm 9+ (ships with Node.js)

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
The frontend dev server proxies `/api` requests to the backend, so set matching ports.

### Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend starts on `http://localhost:3000` and proxies `/api` calls to the backend at `http://localhost:8080`.  
Make sure the backend is running first.

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

## CLI Scripts

Quick reference for the scripts under `scripts/`. They all run with `uv run python scripts/<name>.py`.

| Script | What it does | Common flags |
|---|---|---|
| `bootstrap_library.py` | Pulls books from Gutendex, processes them into `Passage` objects, upserts into Qdrant. | `--max-books 50` `--topics "science,history"` `--dry-run` |
| `test_real_call.py` | Dev-time end-to-end smoke test (hardcoded default blueprint, prints sample questions). Use `generate_test.py` for the real CLI. | none |
| `generate_test.py` | Production CLI: takes a blueprint id, drives the full pipeline (loop → assemble → render PDFs), saves the test to inventory. | `--blueprint <id>` `--no-pdf` `--log-level <LEVEL>` |
| `qdrant_tool.py` | Inspect and manage Qdrant collections: list, search, get, delete passages. | `collections` `stats` `list` `get <id>` `search "..."` `delete <id>` |

Examples:

```bash
# Bootstrap 50 science + history books into Qdrant (writes a stats report on completion)
uv run python scripts/bootstrap_library.py --max-books 50 --topics "science,history"

# Dry-run: same as above but no Qdrant writes — just stats
uv run python scripts/bootstrap_library.py --max-books 5 --dry-run

# Generate one printable test end-to-end (~3-5 min; talks to the LLM through the proxy)
$env:LOG_LEVEL="ERROR"  # quieter output (PowerShell)
uv run python scripts/test_real_call.py

# Or use the real CLI — pick a blueprint, render PDFs, save to inventory
uv run python scripts/generate_test.py --blueprint default_blueprint_v1
uv run python scripts/generate_test.py --blueprint harder_blueprint_v1 --no-pdf  # skip PDFs

# Inspect Qdrant
uv run python scripts/qdrant_tool.py collections
uv run python scripts/qdrant_tool.py stats
uv run python scripts/qdrant_tool.py search "scientific experiment" --limit 5
uv run python scripts/qdrant_tool.py list --limit 20
uv run python scripts/qdrant_tool.py get <passage-uuid>
uv run python scripts/qdrant_tool.py delete <passage-uuid> --force
```

For full flag details and example output, see the dedicated sections below (Bootstrap Library, Qdrant Tool).

## Generating a Test (End-to-End)

The full pipeline: bootstrap passages → run generation loop → assemble → render PDFs.

### One-time setup

```bash
# 1. Start Qdrant (vector DB)
docker compose up -d

# 2. Bootstrap the passage library from Project Gutenberg
uv run python scripts/bootstrap_library.py --max-books 50 --topics "science,history"
# This fills Qdrant with ~50-300 passages. Use --dry-run to preview without upserting.
```

### Option A — manual E2E run (script)

```bash
# Set logging to ERROR to keep the console clean of progress noise
$env:LOG_LEVEL="ERROR"  # PowerShell
# export LOG_LEVEL=ERROR  # bash

uv run python scripts/test_real_call.py
# Runs 25 slots × 1 req/s through the LLM (Mistral Small via the LiteLLM proxy).
# ~3-5 minutes, ends with a summary like:
#   Generated 56 question records
#   Assembled test: 1d015dddb31b - 56 questions, 3 modules
#   Saved test to inventory. All good!
```

Output PDFs land in `data/generated/test_<id>_student.pdf` and `..._teacher.pdf` (renderer is the T14 PDF module).

### Option B — via the API (T16, not built yet)

```bash
# Server
uv run python run.py        # http://127.0.0.1:8000

# In another terminal, start the frontend
cd frontend && npm run dev  # http://localhost:3000
```

### LiteLLM proxy (optional but recommended)

The generation loop calls the LLM through a LiteLLM proxy on `localhost:4000` so the model and rate limit can be swapped without code changes. `litellm_proxy.yaml` at the repo root configures the proxy with model aliases `mistral-small` and `mistral-large`. Point `LITELLM_PROXY_URL`, `LITELLM_MASTER_KEY`, and `LITELLM_MODEL` in your `.env` at the running proxy.

If the proxy is not running, the loop falls back to calling Mistral directly with `MISTRAL_API_KEY`.

### Qdrant inspection

```bash
uv run python scripts/qdrant_tool.py collections
uv run python scripts/qdrant_tool.py stats
uv run python scripts/qdrant_tool.py search "scientific experiment" --limit 5
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

## Bootstrap Library

The bootstrap library script downloads passages from Project Gutenberg, processes them into structured `Passage` objects, and upserts them into Qdrant for vector search. It's the bulk-fill mechanism for the passage database.

### Pipeline

```
                        ┌──────────────────┐
                        │  bootstrap_library.py  │
                        └────────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
   │ fetch_catalogue│  │ fetch_passage  │  │   Qdrant       │
   │ (Gutendex API) │──│   text + clean │  │   upsert       │
   └────────────────┘  └────────────────┘  └────────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ chunk_text() │
                       │ + process    │
                       └──────────────┘
```

A visual diagram is at `docs/diagrams/bootstrap-pipeline.png`.

### Run the Bootstrap

Prerequisites: Qdrant must be running (`docker compose up -d`) and `.env` configured with `MISTRAL_API_KEY`.

```bash
# Process 50 books on science & history topics
uv run python scripts/bootstrap_library.py --max-books 50 --topics "science,history"

# Default: 200 books across science, history, philosophy, literature
uv run python scripts/bootstrap_library.py

# Dry-run (no Qdrant upsert): print stats only
uv run python scripts/bootstrap_library.py --max-books 5 --dry-run
```

### Output

The script prints a stats report on completion:

```
══════════════════════════════════════════════════
  Bootstrap Library — Stats Report
══════════════════════════════════════════════════
  Total books processed : 50
  Total passages        : 324

  Breakdown by type:
    long                 210
    short                114

  Breakdown by category (top 5):
    science              142
    history              98
    philosophy           84

  Average reading level : 9.2
  Total errors          : 3
══════════════════════════════════════════════════
```

Passages are upserted into the Qdrant collections configured in `.env` (`long_passages` / `short_passages` by default).

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--max-books` | `200` | Max books to fetch from catalogue |
| `--topics` | `science,history,philosophy,literature` | Comma-separated search topics |
| `--dry-run` | `false` | Skip Qdrant upsert, only print stats |

## Qdrant Tool

The `scripts/qdrant_tool.py` script lets you inspect, search, and manage passages in the Qdrant vector database.

### Commands

```bash
# Show collections with point counts
uv run python scripts/qdrant_tool.py collections

# Aggregate stats per collection (type/category breakdown, reading level range)
uv run python scripts/qdrant_tool.py stats

# List passages in a collection
uv run python scripts/qdrant_tool.py list --limit 20
uv run python scripts/qdrant_tool.py list --collection short_passages --limit 10

# Get passage details by full UUID
uv run python scripts/qdrant_tool.py get <passage-uuid>

# Semantic search across passages
uv run python scripts/qdrant_tool.py search "climate change" --limit 5
uv run python scripts/qdrant_tool.py search "scientific experiment" --collection long_passages --limit 3

# Search with payload filters
uv run python scripts/qdrant_tool.py search "history" --filters '{"passage_category": "narrative"}'

# Delete a passage by UUID
uv run python scripts/qdrant_tool.py delete <passage-uuid> --force
```

### Example Output

```
$ uv run python scripts/qdrant_tool.py stats

  ==================================================
  long_passages
  ==================================================
  Total passages       : 43
  Average reading level: 10.8
  Average word count   : 283
  Reading level range  : 8.1 - 13.5

  By type:
    long                 43
    short                0

  By category:
    narrative            14    ##############################
    essay                11    #######################
    scientific           9     ###################
    history              5     ##########
    argumentative        4     ########
```

```
$ uv run python scripts/qdrant_tool.py search "scientific experiment" --limit 3

  Search results for: 'scientific experiment'  |  long_passages

  Score | ID           | Type | Category   | Words | Source
  -----------------------------------------------------------------
  0.642 | dd26a5e9-... | long | scientific | 286   | German Science Reader
  0.628 | a11f06fa-... | long | essay      | 297   | Science in the Kitchen
  0.619 | 88b2f8f6-... | long | scientific | 296   | A History of Magic...
```

## Status

| Component | Status |
|-----------|--------|
| Schemas | Done |
| SQLite Storage | Done |
| Blueprint Config + UI | Done |
| Qdrant Vector Store | Done |
| Test Suite (477 tests + 2 skipped on GTK-less Windows) | Done |
| Passage Scraper | Done |
| LLM Generation Pipeline | Done (PR #13) |
| PDF Renderer (student + teacher) | Done (PR #14) |
