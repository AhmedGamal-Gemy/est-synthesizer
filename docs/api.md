# EST Synthesizer — API Reference

Base URL: `http://{HOST}:{PORT}` (default `http://127.0.0.1:8000`)

All endpoints are CORS-enabled (any origin). No authentication required.

---

## Blueprints — `/api/blueprints`

### List all blueprints

```
GET /api/blueprints
```

Returns all blueprints (built-in + custom). Built-in blueprints are read-only.

**Response `200`:**
```json
[
  {
    "id": "default_blueprint_v1",
    "name": "Default Blueprint (85Q)",
    "description": "Standard 3-module EST test",
    "blueprint_json": { ... },
    "is_builtin": true,
    "created_at": "2026-06-23T12:00:00",
    "updated_at": "2026-06-23T12:00:00"
  }
]
```

### Get one blueprint

```
GET /api/blueprints/{bp_id}
```

**Response `200`:**
```json
{
  "id": "default_blueprint_v1",
  "name": "Default Blueprint (85Q)",
  ...
}
```

**`404`** — Blueprint not found.

### Create custom blueprint

```
POST /api/blueprints
```

**Request:**
```json
{
  "name": "My Custom Blueprint",
  "description": "Optional description",
  "blueprint_json": { ... }
}
```

**Response `201`:**
```json
{
  "id": "custom_abc123",
  "name": "My Custom Blueprint",
  ...
}
```

**`422`** — Invalid blueprint structure.  
**`409`** — Conflict (duplicate name, etc.).

### Update custom blueprint

```
PUT /api/blueprints/{bp_id}
```

**Request:** (all fields optional)
```json
{
  "name": "Renamed Blueprint",
  "blueprint_json": { ... }
}
```

**`403`** — Cannot edit built-in blueprint.  
**`404`** — Not found.

### Delete custom blueprint

```
DELETE /api/blueprints/{bp_id}
```

**Response `204`** — No content.  
**`403`** — Cannot delete built-in.  
**`404`** — Not found.

### Duplicate blueprint (built-in → editable copy)

```
POST /api/blueprints/{bp_id}/duplicate
```

Creates an editable copy of any blueprint (including built-in).

**Response `201`:**
```json
{
  "id": "copy_of_default_blueprint_v1",
  "name": "Default Blueprint (85Q) (Copy)",
  "is_builtin": false,
  ...
}
```

**`404`** — Source blueprint not found.

---

## Scraper — `/api/scraper`

### Fetch catalogue

```
GET /api/scraper/catalogue?topics=science,history&max_books=50
```

**Query params:**
| Param | Type | Default | Description |
|---|---|---|---|
| `topics` | string | `null` (uses default topics) | Comma-separated topic keywords |
| `max_books` | int | `200` | Max books to return |

**Response `200`:**
```json
{
  "count": 50,
  "books": [ { "id": 84, "title": "Frankenstein", ... } ]
}
```

### Download and process a single book

```
GET /api/scraper/book/{book_id}
```

**Response `200`:**
```json
{
  "book_id": 84,
  "total_chunks": 45,
  "passages": [ { "id": "...", "text": "...", "word_count": 286, ... } ],
  "skipped_chunks": 3
}
```

### Full pipeline

```
GET /api/scraper/pipeline?max_books=3&topics=science
```

Catalogue → download → process all in one call.

**Response `200`:**
```json
{
  "books_requested": 3,
  "books_processed": 3,
  "total_passages": 87,
  "total_skipped_chunks": 5,
  "results": [ ... ]
}
```

---

## Test Generation — `/api/tests`

### Start generation

```
POST /api/tests/generate
```

Triggers the full generation pipeline in the background:
1. Retrieve passages from Qdrant
2. Call LLM (Mistral Small via LiteLLM proxy) for each question slot
3. Validate and retry failed slots
4. Assemble questions into a structured test
5. Render student + teacher PDFs
6. Save to inventory

**Request:**
```json
{
  "blueprint_id": "default_blueprint_v1"
}
```

`blueprint_id` is optional. Falls back to `DEFAULT_BLUEPRINT` if omitted or not found in DB.

**Response `202`:**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "pending"
}
```

The `job_id` is used to poll progress.

### Poll job status (polling)

```
GET /api/tests/{job_id}/status
```

**Response `200`:**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "generating",
  "progress": 42,
  "result_test_id": null,
  "error_message": null
}
```

**Status values:** `pending` → `generating` → `completed` | `failed`

`progress` is 0–100. When `status` is `completed`, `result_test_id` is set (but may be null — use the test inventory to look up the test by job_id).

### SSE real-time progress

```
GET /api/tests/{job_id}/progress
```

Server-Sent Events stream. The frontend connects with `EventSource` (or `fetch` + `ReadableStream`) and receives events as the job progresses.

**Events:**

```
event: progress
data: {"job_id":"a1b2c3d4e5f6","status":"generating","progress":42,
       "result_test_id":null,"error_message":null}

event: complete
data: {"job_id":"a1b2c3d4e5f6","status":"completed","progress":100,
       "result_test_id":"abc123","error_message":null}

event: error
data: {"job_id":"a1b2c3d4e5f6","status":"failed","progress":0,
       "result_test_id":null,"error_message":"No questions generated"}
```

**Frontend usage (JS):**
```javascript
const sse = new EventSource(`http://localhost:8000/api/tests/${jobId}/progress`);

sse.addEventListener("progress", (e) => {
  const data = JSON.parse(e.data);
  updateProgressBar(data.progress);
});

sse.addEventListener("complete", (e) => {
  const data = JSON.parse(e.data);
  showDownloadLinks(data.result_test_id);
  sse.close();
});

sse.addEventListener("error", (e) => {
  const data = JSON.parse(e.data);
  showError(data.error_message);
  sse.close();
});
```

**`404`** — Job not found.

---

## Feedback — `/api/tests`

### Submit feedback for a question

```
POST /api/tests/{test_id}/questions/{question_id}/feedback
```

**Request:**
```json
{
  "rating": 4,
  "flags": ["good"],
  "notes": "Clear question, good distractors"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `rating` | int | ✅ | 1–5 quality rating |
| `flags` | array[string] | No | See flag values below |
| `notes` | string or null | No | Free-form reviewer notes |

**Flag values:** `good`, `too_easy`, `too_hard`, `ambiguous`, `wrong_answer`, `distractor_weak`, `passage_mismatch`, `typo`

**Response `201`:**
```json
{
  "success": true,
  "feedback_id": "f1e2d3c4b5a6"
}
```

**`400`** — Invalid rating (not 1–5).

### List feedback for a test

```
GET /api/tests/{test_id}/feedback
```

Returns all feedback records, newest first.

**Response `200`:**
```json
[
  {
    "id": "f1e2d3c4b5a6",
    "test_id": "abc123",
    "question_id": "q1w2e3r4t5y6",
    "rating": 4,
    "flags": ["good"],
    "notes": "Clear question, good distractors",
    "created_at": "2026-06-23T12:00:00"
  }
]
```

---

## Scraper — `/api/scraper`

_(See Scraper section above)_

---

## Config & Health

### Server config

```
GET /api/config
```

**Response `200`:**
```json
{
  "host": "127.0.0.1",
  "port": 8000,
  "api_base": "http://127.0.0.1:8000"
}
```

### Health check

```
GET /health
```

**Response `200`:**
```json
{
  "status": "ok"
}
```

---

## Generation Flow (Frontend Integration)

The typical frontend flow for generating a test:

```
1. [Optional] GET /api/blueprints
   → Show list of available blueprints, let user pick one.

2. POST /api/tests/generate  { "blueprint_id": "..." }
   → Returns { job_id, status: "pending" }

3. GET /api/tests/{job_id}/progress (SSE)
   → Show progress bar, update in real time.
   → On "complete" event: show download/result.
   → On "error" event: show error message.

4. [Optional] GET /api/tests/{test_id}/feedback
   → Show existing feedback if any.

5. [Optional] POST /api/tests/{test_id}/questions/{question_id}/feedback
   → Submit teacher rating.
```

The SSE endpoint is the recommended approach for step 3. If SSE is not feasible, poll `GET /api/tests/{job_id}/status` every 1–2 seconds instead.

---

## Frontend Setup

### Dev server

The Vite frontend on `localhost:3000` proxies `/api` requests to the backend at `localhost:8080`. Configured in `frontend/vite.config.js`:

```js
proxy: {
  "/api": { target: "http://localhost:8080", changeOrigin: true },
}
```

Make sure the backend starts on `8080` (set `PORT=8080` in `.env`) and the frontend on `3000`.

### API client

The frontend uses `axios`. Existing client at `frontend/src/api/client.js` with base URL configured via Vite proxy. Import endpoints from `frontend/src/api/*.js`.

---

## Error Responses

All errors follow FastAPI's standard format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|---|---|
| `400` | Bad request (invalid input) |
| `403` | Forbidden (e.g., editing a built-in blueprint) |
| `404` | Not found |
| `409` | Conflict |
| `422` | Unprocessable (validation error) |
| `500` | Internal server error |
| `502` | Bad gateway (e.g., Gutendex unreachable) |
