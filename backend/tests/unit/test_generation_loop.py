"""Unit tests for backend.app.generation.loop — generation loop orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.generation.loop import (
    GenerationFailedError,
    run_generation_loop,
)
from backend.app.schemas import (
    Difficulty,
    ModuleConfig,
    ModuleSlot,
    ModuleType,
    SkillType,
    TestBlueprint,
)
from backend.app.schemas.enums import Difficulty, DistractorRole, SkillType
from backend.app.schemas.question import LLMQuestionOutput


# ── Helpers ──────────────────────────────────────────────────

_E = Difficulty.EASY
_M = Difficulty.MEDIUM


def _make_blueprint() -> TestBlueprint:
    """Minimal blueprint with 2 modules, 3 slots total."""
    return TestBlueprint(
        id="test_bp",
        name="Test Blueprint",
        modules=[
            ModuleConfig(
                module_number=1,
                module_type=ModuleType.WRITING,
                slots=[
                    ModuleSlot(
                        slot_number=1,
                        skill_type=SkillType.SENTENCE_FORMATION,
                        difficulty=_E,
                        question_count=2,
                        easy_count=2,
                        medium_count=0,
                        hard_count=0,
                    ),
                ],
                has_figure=False,
                wordy_answer_style=True,
            ),
            ModuleConfig(
                module_number=2,
                module_type=ModuleType.READING_SHORT,
                slots=[
                    ModuleSlot(
                        slot_number=1,
                        skill_type=SkillType.VOCABULARY_IN_CONTEXT,
                        difficulty=_E,
                        question_count=1,
                        easy_count=1,
                        medium_count=0,
                        hard_count=0,
                    ),
                    ModuleSlot(
                        slot_number=2,
                        skill_type=SkillType.INFORMATION_AND_IDEAS,
                        difficulty=_M,
                        question_count=1,
                        easy_count=0,
                        medium_count=1,
                        hard_count=0,
                    ),
                ],
                has_figure=False,
                wordy_answer_style=False,
            ),
        ],
        total_questions=4,
        difficulty_distribution={"easy": 0.5, "medium": 0.5, "hard": 0.0},
    )


def _fake_passage_payload(passage_id: str, text: str = "Some passage text for testing.") -> dict:
    return {
        "id": passage_id,
        "payload": {
            "text": text,
            "source_url": "http://example.com",
            "source_title": "Test",
            "passage_type": "long",
            "passage_category": "essay",
            "word_count": 100,
            "reading_level": 10.0,
        },
        "score": 0.95,
    }


def _fake_llm_response(question_text: str = "What is the answer?") -> dict:
    """Simulate a successful LLM response as parsed JSON."""
    return {
        "reasoning": "This is a simple test passage.",
        "questions": [
            {
                "question_text": question_text,
                "choices": [
                    {"letter": "A", "text": "Choice A", "distractor_role": DistractorRole.BEST_ANSWER},
                    {"letter": "B", "text": "Choice B", "distractor_role": DistractorRole.GOOD_NOT_BEST},
                    {"letter": "C", "text": "Choice C", "distractor_role": DistractorRole.COMPLETELY_WRONG},
                    {"letter": "D", "text": "Choice D", "distractor_role": DistractorRole.COMPLETELY_WRONG},
                ],
                "correct_answer": "A",
                "explanation": "Because A is correct.",
                "supporting_line": "Some passage text for testing.",
                "skill_type": SkillType.SENTENCE_FORMATION,
                "difficulty": Difficulty.EASY,
            }
        ],
    }


# ── Tests ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_jobs():
    """Prevent any real DB calls from job storage."""
    with patch("backend.app.generation.loop.update_job_status", new=AsyncMock()):
        yield


@pytest.fixture
def mock_qdrant():
    """Return passages for each slot."""
    instances = []
    original = __import__("backend.app.storage.qdrant", fromlist=["QdrantManager"]).QdrantManager

    def _constructor(*args, **kwargs):
        inst = MagicMock(spec=original)
        inst.close = AsyncMock()
        inst.search_passages = AsyncMock(
            side_effect=lambda query_text, collection, filters, limit: [
                _fake_passage_payload(
                    f"passage-{collection}-{hash(query_text)}-{i}",
                    text="Some passage text for testing.",
                )
                for i in range(limit)
            ]
        )
        instances.append(inst)
        return inst

    with patch("backend.app.generation.loop.QdrantManager", side_effect=_constructor) as patched:
        yield patched, instances


@pytest.fixture
def mock_llm():
    """Return valid LLM responses."""
    with patch("backend.app.generation.caller.LLMQueue.submit", new=AsyncMock()) as mock_submit:
        mock_submit.return_value = _fake_llm_response()
        yield mock_submit


# ── Successful generation ────────────────────────────────────


@pytest.mark.asyncio
async def test_generates_all_slots(mock_qdrant, mock_llm):
    blueprint = _make_blueprint()
    results = await run_generation_loop(blueprint, "job-001")
    # 3 slots → all succeed with 1 question each → but slot 1 has 2 questions
    # Actually the LLM always returns 1 question regardless of slot question_count
    # So we get 1 per slot = 3 results
    assert len(results) == 3
    for r in results:
        assert "question" in r
        assert r["question"].correct_answer == "A"


@pytest.mark.asyncio
async def test_returns_correct_metadata(mock_qdrant, mock_llm):
    blueprint = _make_blueprint()
    results = await run_generation_loop(blueprint, "job-002")
    for r in results:
        assert r["passage_id"].startswith("passage-")
        assert r["module_number"] in (1, 2)
        assert r["slot_number"] >= 1


# ── Handling failures ────────────────────────────────────────


@pytest.mark.asyncio
async def test_fails_when_threshold_exceeded(mock_qdrant):
    """All LLM calls fail — should raise."""
    with patch("backend.app.generation.caller.LLMQueue.submit", new=AsyncMock()) as mock_submit:
        from backend.app.generation.exceptions import LLMAPIError
        mock_submit.side_effect = LLMAPIError("API error")

        blueprint = _make_blueprint()
        with pytest.raises(GenerationFailedError):
            await run_generation_loop(blueprint, "job-003")


@pytest.mark.asyncio
async def test_retries_on_llm_error(mock_qdrant):
    """Fail once, succeed on retry."""
    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from backend.app.generation.exceptions import LLMAPIError
            raise LLMAPIError("Temp error")
        return _fake_llm_response()

    with patch("backend.app.generation.caller.LLMQueue.submit", new=AsyncMock(side_effect=_side_effect)):
        blueprint = _make_blueprint()
        results = await run_generation_loop(blueprint, "job-004")
        assert len(results) == 3
        assert call_count == 4  # 1 fail + retry for slot 1, then 3 more calls for 3 slots... 
        # Actually: slot 1 (1 fail + 1 success = 2), slot 2 (1 success = 1), slot 3 (1 success = 1) = 4


# ── Passage retrieval failures ───────────────────────────────


@pytest.mark.asyncio
async def test_skips_slot_with_no_passage(mock_llm):
    """When Qdrant returns no passage for a slot, it's counted as failed."""
    with patch("backend.app.generation.loop.QdrantManager") as mock_qdrant_cls:
        instance = MagicMock()
        instance.search_passages = AsyncMock(return_value=[])
        instance.close = AsyncMock()
        mock_qdrant_cls.return_value = instance

        blueprint = _make_blueprint()
        with pytest.raises(GenerationFailedError):
            await run_generation_loop(blueprint, "job-005")


@pytest.mark.asyncio
async def test_empty_llm_response_retries(mock_qdrant):
    """Empty questions array in LLM response exhausts retries → all slots fail."""
    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return {"reasoning": "No valid questions.", "questions": []}

    with patch("backend.app.generation.caller.LLMQueue.submit", new=AsyncMock(side_effect=_side_effect)):
        blueprint = _make_blueprint()
        with pytest.raises(GenerationFailedError):
            await run_generation_loop(blueprint, "job-006")
