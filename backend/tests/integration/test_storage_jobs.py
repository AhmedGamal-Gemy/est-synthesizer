"""Integration tests for backend.app.storage.jobs — GenerationJob CRUD."""

from datetime import datetime, timezone

import pytest

from backend.app.schemas import GenerationJob, JobStatus


# ── helpers ──────────────────────────────────────────────────


def _make_job(**overrides) -> GenerationJob:
    defaults = {
        "id": "job-001",
        "status": JobStatus.PENDING,
        "blueprint_id": "default_blueprint_v1",
        "total_slots": 5,
        "completed_slots": 0,
        "failed_slots": 0,
        "result_test_id": None,
        "error_message": None,
        "created_at": datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return GenerationJob(**defaults)


# ── monkeypatch fixture ──────────────────────────────────────


@pytest.fixture
async def db_conn_for_jobs():
    """In-memory SQLite with schema + monkeypatched db module."""
    import aiosqlite
    import backend.app.storage.db as db_mod

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(db_mod.SCHEMA_SQL)
    await conn.commit()

    original_conn = db_mod._conn
    original_path = db_mod.DB_PATH
    db_mod._conn = conn
    db_mod.DB_PATH = ":memory:"
    yield conn
    db_mod._conn = original_conn
    db_mod.DB_PATH = original_path
    await conn.close()


# ── CRUD tests ───────────────────────────────────────────────


class TestCreateAndGetJob:
    async def test_create_then_get_roundtrip(self, db_conn_for_jobs):
        from backend.app.storage.jobs import create_job, get_job

        job = _make_job()
        await create_job(job)

        fetched = await get_job(job.id)
        assert fetched is not None
        assert fetched.id == job.id
        assert fetched.status == JobStatus.PENDING
        assert fetched.blueprint_id == job.blueprint_id
        assert fetched.total_slots == 5
        assert fetched.completed_slots == 0
        assert fetched.failed_slots == 0
        assert fetched.result_test_id is None
        assert fetched.error_message is None

    async def test_get_job_returns_none_for_nonexistent_id(self, db_conn_for_jobs):
        from backend.app.storage.jobs import get_job

        result = await get_job("nonexistent-id")
        assert result is None


class TestUpdateJobStatus:
    async def test_update_status_from_pending_to_generating(self, db_conn_for_jobs):
        from backend.app.storage.jobs import create_job, get_job, update_job_status

        job = _make_job()
        await create_job(job)

        await update_job_status(job.id, JobStatus.GENERATING)

        fetched = await get_job(job.id)
        assert fetched is not None
        assert fetched.status == JobStatus.GENERATING

    async def test_completed_slots_increment_with_coalesce(self, db_conn_for_jobs):
        from backend.app.storage.jobs import create_job, get_job, update_job_status

        job = _make_job()
        await create_job(job)

        # Increment completed_slots by 3
        await update_job_status(
            job.id, JobStatus.GENERATING, completed_slots=3
        )

        fetched = await get_job(job.id)
        assert fetched.completed_slots == 3  # 0 + 3 = 3

    async def test_failed_slots_increment_with_coalesce(self, db_conn_for_jobs):
        from backend.app.storage.jobs import create_job, get_job, update_job_status

        job = _make_job()
        await create_job(job)

        # Increment both completed and failed
        await update_job_status(
            job.id, JobStatus.GENERATING, completed_slots=2, failed_slots=1
        )

        fetched = await get_job(job.id)
        assert fetched.completed_slots == 2
        assert fetched.failed_slots == 1

    async def test_coalesce_none_means_no_increment(self, db_conn_for_jobs):
        from backend.app.storage.jobs import create_job, get_job, update_job_status

        job = _make_job(completed_slots=3, failed_slots=1)
        await create_job(job)

        # Update status without passing completed_slots/failed_slots
        await update_job_status(job.id, JobStatus.ASSEMBLING)

        fetched = await get_job(job.id)
        assert fetched.completed_slots == 3  # unchanged — COALESCE(NULL, 0)=0
        assert fetched.failed_slots == 1     # unchanged

    async def test_update_with_error_message(self, db_conn_for_jobs):
        from backend.app.storage.jobs import create_job, get_job, update_job_status

        job = _make_job()
        await create_job(job)

        await update_job_status(
            job.id, JobStatus.FAILED,
            error_message="Something went wrong"
        )

        fetched = await get_job(job.id)
        assert fetched.status == JobStatus.FAILED
        assert fetched.error_message == "Something went wrong"
