"""Unit tests for backend.app.schemas.job — GenerationJob model."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.enums import JobStatus
from backend.app.schemas.job import GenerationJob


# ── Helpers ──────────────────────────────────────────────────

def _valid_job(**overrides) -> dict:
    base = {
        "id": "j-001",
        "status": JobStatus.PENDING,
        "blueprint_id": "bp-001",
        "total_slots": 85,
        "completed_slots": 0,
        "failed_slots": 0,
    }
    base.update(overrides)
    return base


# ── GenerationJob — creation ─────────────────────────────────

def test_generation_job_creation():
    j = GenerationJob(**_valid_job())
    assert j.id == "j-001"
    assert j.status == JobStatus.PENDING
    assert j.blueprint_id == "bp-001"
    assert j.total_slots == 85
    assert j.completed_slots == 0
    assert j.failed_slots == 0


def test_generation_job_missing_required_field():
    for missing in ["id", "status", "blueprint_id", "total_slots", "completed_slots", "failed_slots"]:
        kwargs = _valid_job()
        del kwargs[missing]
        with pytest.raises(ValidationError):
            GenerationJob(**kwargs)


# ── GenerationJob — progress property ────────────────────────

def test_generation_job_progress_zero_total_slots():
    j = GenerationJob(**_valid_job(total_slots=0, completed_slots=0))
    assert j.progress == 0


def test_generation_job_progress_partial_completion():
    # 42/85 * 100 = 49.411... → int truncation → 49
    j = GenerationJob(**_valid_job(total_slots=85, completed_slots=42))
    assert j.progress == 49


def test_generation_job_progress_full_completion():
    j = GenerationJob(**_valid_job(total_slots=85, completed_slots=85))
    assert j.progress == 100


def test_generation_job_progress_small_numbers():
    j = GenerationJob(**_valid_job(total_slots=4, completed_slots=1))
    # 1/4 * 100 = 25
    assert j.progress == 25


def test_generation_job_progress_rounds_down():
    # 1/3 * 100 = 33.33 → 33
    j = GenerationJob(**_valid_job(total_slots=3, completed_slots=1))
    assert j.progress == 33


# ── GenerationJob — field constraints (ge=0) ─────────────────

def test_generation_job_total_slots_ge0_valid():
    j = GenerationJob(**_valid_job(total_slots=0))
    assert j.total_slots == 0


def test_generation_job_total_slots_negative_invalid():
    with pytest.raises(ValidationError):
        GenerationJob(**_valid_job(total_slots=-1))


def test_generation_job_completed_slots_ge0_valid():
    j = GenerationJob(**_valid_job(completed_slots=0))
    assert j.completed_slots == 0


def test_generation_job_completed_slots_negative_invalid():
    with pytest.raises(ValidationError):
        GenerationJob(**_valid_job(completed_slots=-1))


def test_generation_job_failed_slots_ge0_valid():
    j = GenerationJob(**_valid_job(failed_slots=0))
    assert j.failed_slots == 0


def test_generation_job_failed_slots_negative_invalid():
    with pytest.raises(ValidationError):
        GenerationJob(**_valid_job(failed_slots=-1))


# ── GenerationJob — optional fields ──────────────────────────

def test_generation_job_result_test_id_default_none():
    j = GenerationJob(**_valid_job())
    assert j.result_test_id is None


def test_generation_job_error_message_default_none():
    j = GenerationJob(**_valid_job())
    assert j.error_message is None


def test_generation_job_result_test_id_explicit():
    j = GenerationJob(**_valid_job(result_test_id="t-001"))
    assert j.result_test_id == "t-001"


# ── GenerationJob — created_at / updated_at auto-populate ────

def test_generation_job_created_at_auto_populates():
    j = GenerationJob(**_valid_job())
    assert j.created_at is not None
    assert j.created_at.tzinfo is not None


def test_generation_job_updated_at_auto_populates():
    j = GenerationJob(**_valid_job())
    assert j.updated_at is not None
    assert j.updated_at.tzinfo is not None


# ── GenerationJob — repr ─────────────────────────────────────

def test_generation_job_repr_includes_progress():
    j = GenerationJob(**_valid_job(total_slots=85, completed_slots=42))
    r = repr(j)
    assert "GenerationJob" in r
    assert "progress=49%" in r
    assert "status=" in r


def test_generation_job_repr_includes_id():
    j = GenerationJob(**_valid_job(id="j-abc"))
    assert "j-abc" in repr(j)


# ── GenerationJob — status enum acceptance ───────────────────

def test_generation_job_status_accepts_enum():
    for status in JobStatus:
        j = GenerationJob(**_valid_job(status=status))
        assert j.status == status


def test_generation_job_status_strict_rejects_string():
    """strict=True requires actual enum instances, not string values."""
    with pytest.raises(ValidationError):
        GenerationJob(**_valid_job(status="pending"))


# ── GenerationJob — strict mode ──────────────────────────────

def test_generation_job_extra_fields_ignored_with_strict():
    """strict=True enforces strict types but does NOT forbid extra fields."""
    j = GenerationJob(**_valid_job(extra_field="ignored"))
    assert j.id == "j-001"
