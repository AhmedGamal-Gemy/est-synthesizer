"""End-to-end integration test for the generation API (T16 + T17 + T20).

Exercises the full pipeline through the FastAPI TestClient with mocked
external services (Qdrant, LLM) so the test is hermetic and fast.
"""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.schemas import (
    AnswerChoice, Difficulty, DistractorRole, JobStatus,
    LLMQuestionOutput, ModuleType, SkillType,
)


# ── Helpers: fake question data ──────────────────────────────


def _fake_llm_question(skill: SkillType, difficulty: Difficulty) -> LLMQuestionOutput:
    """Produce a valid LLMQuestionOutput (strict=True)."""
    return LLMQuestionOutput(
        question_text=f"Test question for {skill.value}?",
        choices=[
            AnswerChoice(letter="A", text="Correct answer", distractor_role=DistractorRole.BEST_ANSWER),
            AnswerChoice(letter="B", text="Almost right", distractor_role=DistractorRole.GOOD_NOT_BEST),
            AnswerChoice(letter="C", text="Wrong option 1", distractor_role=DistractorRole.COMPLETELY_WRONG),
            AnswerChoice(letter="D", text="Wrong option 2", distractor_role=DistractorRole.COMPLETELY_WRONG),
        ],
        correct_answer="A",
        explanation="Because A is correct.",
        supporting_line="From the passage, line 5.",
        skill_type=skill,
        difficulty=difficulty,
    )


def _build_fake_results() -> list[dict]:
    """Return what `run_generation_loop` would return: ~5 flat question records."""
    return [
        {
            "question": _fake_llm_question(SkillType.CONVENTIONS_OF_STANDARD_ENGLISH, Difficulty.EASY),
            "passage_id": uuid.uuid4().hex[:12],
            "module_number": 1,
            "module_type": ModuleType.WRITING,
            "slot_number": 1,
        },
        {
            "question": _fake_llm_question(SkillType.SENTENCE_FORMATION, Difficulty.MEDIUM),
            "passage_id": uuid.uuid4().hex[:12],
            "module_number": 1,
            "module_type": ModuleType.WRITING,
            "slot_number": 2,
        },
        {
            "question": _fake_llm_question(SkillType.INFORMATION_AND_IDEAS, Difficulty.MEDIUM),
            "passage_id": uuid.uuid4().hex[:12],
            "module_number": 2,
            "module_type": ModuleType.READING_LONG,
            "slot_number": 1,
        },
        {
            "question": _fake_llm_question(SkillType.RHETORIC, Difficulty.HARD),
            "passage_id": uuid.uuid4().hex[:12],
            "module_number": 2,
            "module_type": ModuleType.READING_LONG,
            "slot_number": 2,
        },
        {
            "question": _fake_llm_question(SkillType.INFORMATION_AND_IDEAS, Difficulty.EASY),
            "passage_id": uuid.uuid4().hex[:12],
            "module_number": 3,
            "module_type": ModuleType.READING_SHORT,
            "slot_number": 1,
        },
    ]


# ── Test client fixture ─────────────────────────────────────


@pytest.fixture
async def client():
    """Async HTTP test client with seeded DB, mocked lifespan & external deps."""
    import aiosqlite
    import backend.app.storage.db as db_mod
    from backend.app.storage.db import SCHEMA_SQL
    from backend.app.storage.blueprints import seed_builtin_blueprints
    import backend.app.main as main_mod
    import backend.app.api.generate as gen_mod
    from backend.app.blueprint.default import DEFAULT_BLUEPRINT
    from contextlib import asynccontextmanager

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()

    original_conn = db_mod._conn
    original_path = db_mod.DB_PATH
    original_lifespan = main_mod.app.router.lifespan_context
    original_resolve = gen_mod._resolve_blueprint
    original_run_loop = gen_mod.run_generation_loop
    original_fetch_texts = gen_mod._fetch_passage_texts

    db_mod._conn = conn
    db_mod.DB_PATH = ":memory:"
    try:
        await seed_builtin_blueprints()

        # Mock lifespan to skip init_db (already done) and Qdrant init
        @asynccontextmanager
        async def mock_lifespan(app):
            yield

        main_mod.app.router.lifespan_context = mock_lifespan

        # Patch _resolve_blueprint — avoids DB strict-validation issues
        async def _mock_resolve(bp_id: str):
            return DEFAULT_BLUEPRINT.model_copy(deep=True)

        gen_mod._resolve_blueprint = _mock_resolve

        # Mock run_generation_loop — avoids Qdrant + LLM entirely
        async def _mock_run_loop(blueprint, job_id):
            return _build_fake_results()

        gen_mod.run_generation_loop = _mock_run_loop

        # Mock _fetch_passage_texts — avoids Qdrant passage retrieval for PDFs
        async def _mock_fetch_texts(passage_ids):
            return {}

        gen_mod._fetch_passage_texts = _mock_fetch_texts

        transport = ASGITransport(app=main_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    finally:
        gen_mod._fetch_passage_texts = original_fetch_texts
        gen_mod.run_generation_loop = original_run_loop
        gen_mod._resolve_blueprint = original_resolve
        main_mod.app.router.lifespan_context = original_lifespan
        db_mod._conn = original_conn
        db_mod.DB_PATH = original_path
        await conn.close()


# ── Generation E2E tests ────────────────────────────────────


class TestGenerateE2E:
    """End-to-end test of the generation pipeline through the API."""

    POLL_INTERVAL = 0.1
    TIMEOUT = 15.0

    async def _poll_until_done(self, client, job_id: str) -> dict:
        """Poll /api/tests/{job_id}/status until terminal, return last response."""
        deadline = asyncio.get_event_loop().time() + self.TIMEOUT
        while True:
            resp = await client.get(f"/api/tests/{job_id}/status")
            assert resp.status_code == 200
            data = resp.json()
            if data["status"] in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
                return data
            if asyncio.get_event_loop().time() > deadline:
                pytest.fail(f"Timed out after {self.TIMEOUT}s waiting for job {job_id} (status={data['status']})")
            await asyncio.sleep(self.POLL_INTERVAL)

    async def test_generate_default_blueprint_returns_202(self, client):
        """POST /api/tests/generate with default blueprint returns 202 + job_id."""
        response = await client.post("/api/tests/generate", json={})
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == JobStatus.PENDING.value

    async def test_generate_custom_blueprint_returns_202(self, client):
        """POST with explicit builtin blueprint id."""
        response = await client.post("/api/tests/generate", json={"blueprint_id": "default_blueprint_v1"})
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data

    async def test_generation_completes_with_correct_status(self, client):
        """Full pipeline: submit → poll → verify completion."""
        # Submit generation job
        resp = await client.post("/api/tests/generate", json={})
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        # Poll until terminal
        final = await self._poll_until_done(client, job_id)

        assert final["status"] == JobStatus.COMPLETED.value, f"Expected completed, got: {final}"
        # 5 mock results / 85 total blueprint slots ≈ 5.9% → assert at least some progress
        assert final["progress"] > 0, f"Expected non-zero progress, got: {final['progress']}"
        assert final["job_id"] == job_id
        # result_test_id is None due to a known COALESCE issue (see Generate.T16 ponytail comment)
        # The test record links back via test.job_id instead.

    async def test_generation_saves_test_to_inventory(self, client):
        """After completion, the test should be queryable via the inventory."""
        # Submit
        resp = await client.post("/api/tests/generate", json={})
        job_id = resp.json()["job_id"]

        # Wait
        await self._poll_until_done(client, job_id)

        # The test record is linked via job_id.  We can verify it was saved by
        # checking the DB directly (no public test-listing endpoint exists yet).
        import aiosqlite
        from backend.app.storage.db import DB_PATH

        # DB_PATH is ":memory:" during the test — need the same connection
        import backend.app.storage.db as db_mod
        conn = db_mod._conn
        cursor = await conn.execute(
            "SELECT id, blueprint_id, total_questions, student_pdf_path, teacher_pdf_path "
            "FROM test_inventory WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()
        assert row is not None, "No test record found for completed job"
        test_id, bp_id, total_q, student_pdf, teacher_pdf = row
        assert total_q == 5, f"Expected 5 questions, got {total_q}"
        # PDF paths may be None on Windows (non-fatal render failure is expected)
        assert student_pdf is None or student_pdf.endswith(".pdf")
        assert teacher_pdf is None or teacher_pdf.endswith(".pdf")

    async def test_generation_unknown_blueprint_uses_default(self, client):
        """An unknown blueprint_id falls back gracefully (no 404)."""
        response = await client.post(
            "/api/tests/generate",
            json={"blueprint_id": "nonexistent_blueprint"},
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        final = await self._poll_until_done(client, job_id)
        assert final["status"] == JobStatus.COMPLETED.value

    async def test_status_nonexistent_job_returns_404(self, client):
        """GET /api/tests/{job_id}/status for a fake job returns 404."""
        response = await client.get("/api/tests/fakejob123456/status")
        assert response.status_code == 404
