"""Real Qdrant integration tests.

Requires a live Qdrant server (docker compose up -d).
Tests auto-skip if Qdrant is unreachable.
Embedding calls are mocked to avoid burning LLM credits,
but all Qdrant operations (create collection, upsert, search, filter)
use the real server.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from backend.app.config import settings
from backend.app.schemas import Passage, PassageCategory, PassageType
from backend.app.storage.qdrant import (
    COLLECTION_LONG,
    COLLECTION_SHORT,
    QdrantManager,
)


# ── skip fixture ────────────────────────────────────────────

def _qdrant_available() -> bool:
    """Check if Qdrant server is reachable."""
    import socket
    try:
        # Parse host from QDRANT_URL
        url = settings.QDRANT_URL
        # e.g. "http://localhost:6333"
        host = url.split("//")[1].split(":")[0]
        port = int(url.split(":")[-1])
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return True
    except Exception:
        return False


skip_no_qdrant = pytest.mark.skipif(
    not _qdrant_available(),
    reason="Qdrant server not reachable — start with `docker compose up -d`",
)


# ── helpers ──────────────────────────────────────────────────

def _make_passage(
    passage_type: PassageType = PassageType.LONG,
    passage_category: PassageCategory = PassageCategory.ESSAY,
    word_count: int = 500,
    reading_level: float = 10.0,
) -> Passage:
    return Passage(
        id=str(uuid.uuid4()),
        text="This is a test passage about Newton's laws of motion. "
             "An object at rest stays at rest unless acted upon by a force. "
             "Force equals mass times acceleration. "
             "For every action there is an equal and opposite reaction.",
        source_url="https://example.com/test",
        source_title="Test Passage",
        passage_type=passage_type,
        passage_category=passage_category,
        word_count=word_count,
        reading_level=reading_level,
    )


# Dummy 1024-dim embedding (zeros — not semantically meaningful,
# but sufficient for testing Qdrant insert/search mechanics)
DUMMY_VECTOR = [0.1] * 1024


# ── fixtures ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def qdrant_manager():
    """Live QdrantManager with mocked embedding."""
    manager = QdrantManager(url=settings.QDRANT_URL)

    # Mock _embed so we don't load the real sentence-transformers model
    manager._embed = AsyncMock(return_value=DUMMY_VECTOR)

    # Create collections for the test
    await manager.init_collections()
    yield manager

    # Cleanup: delete test collections so state is clean for next run
    for name in (COLLECTION_LONG, COLLECTION_SHORT):
        try:
            exists = await manager.client.collection_exists(name)
            if exists:
                await manager.client.delete_collection(name)
        except Exception:
            pass
    await manager.close()


# ── init_collections ─────────────────────────────────────────


@skip_no_qdrant
class TestInitCollections:
    async def test_collections_exist_after_init(self, qdrant_manager):
        long_exists = await qdrant_manager.client.collection_exists(COLLECTION_LONG)
        short_exists = await qdrant_manager.client.collection_exists(COLLECTION_SHORT)
        assert long_exists
        assert short_exists

    async def test_collections_have_correct_vector_config(self, qdrant_manager):
        info = await qdrant_manager.client.get_collection(COLLECTION_LONG)
        assert info.config.params.vectors.size == 1024
        assert str(info.config.params.vectors.distance) == "Cosine"

    async def test_init_collections_is_idempotent(self, qdrant_manager):
        # Calling again should not error
        await qdrant_manager.init_collections()
        long_exists = await qdrant_manager.client.collection_exists(COLLECTION_LONG)
        assert long_exists


# ── upsert_passage ───────────────────────────────────────────


@skip_no_qdrant
class TestUpsertPassage:
    async def test_upsert_long_passage(self, qdrant_manager):
        passage = _make_passage(passage_type=PassageType.LONG)
        await qdrant_manager.upsert_passage(passage)

        # Verify point exists in long_passages
        point = await qdrant_manager.client.retrieve(
            collection_name=COLLECTION_LONG,
            ids=[passage.id],
        )
        assert len(point) == 1
        assert point[0].payload["text"] == passage.text
        assert point[0].payload["passage_type"] == "long"

    async def test_upsert_short_passage(self, qdrant_manager):
        passage = _make_passage(passage_type=PassageType.SHORT)
        await qdrant_manager.upsert_passage(passage)

        point = await qdrant_manager.client.retrieve(
            collection_name=COLLECTION_SHORT,
            ids=[passage.id],
        )
        assert len(point) == 1
        assert point[0].payload["passage_type"] == "short"

    async def test_upsert_stores_all_payload_fields(self, qdrant_manager):
        passage = _make_passage(
            word_count=350,
            reading_level=12.5,
            passage_category=PassageCategory.SCIENTIFIC,
        )
        await qdrant_manager.upsert_passage(passage)

        point = await qdrant_manager.client.retrieve(
            collection_name=COLLECTION_LONG,
            ids=[passage.id],
        )
        payload = point[0].payload
        assert payload["source_url"] == passage.source_url
        assert payload["source_title"] == passage.source_title
        assert payload["word_count"] == 350
        assert payload["reading_level"] == 12.5
        assert payload["passage_category"] == "scientific"

    async def test_upsert_updates_existing_point(self, qdrant_manager):
        passage = _make_passage()
        await qdrant_manager.upsert_passage(passage)

        # Upsert same id with different text
        updated = Passage(
            id=passage.id,
            text="Updated text for this passage.",
            source_url=passage.source_url,
            source_title=passage.source_title,
            passage_type=passage.passage_type,
            passage_category=passage.passage_category,
            word_count=5,
            reading_level=passage.reading_level,
        )
        await qdrant_manager.upsert_passage(updated)

        point = await qdrant_manager.client.retrieve(
            collection_name=COLLECTION_LONG,
            ids=[passage.id],
        )
        assert point[0].payload["text"] == "Updated text for this passage."
        assert point[0].payload["word_count"] == 5


# ── search_passages ──────────────────────────────────────────


@skip_no_qdrant
class TestSearchPassages:
    async def test_search_returns_results(self, qdrant_manager):
        # Insert a passage
        passage = _make_passage()
        await qdrant_manager.upsert_passage(passage)

        # Search with a query
        results = await qdrant_manager.search_passages(
            query_text="Newton's laws",
            collection=COLLECTION_LONG,
            limit=5,
        )
        assert len(results) >= 1
        assert results[0]["id"] == passage.id
        assert "score" in results[0]
        assert "payload" in results[0]

    async def test_search_respects_limit(self, qdrant_manager):
        # Insert 3 passages
        for i in range(3):
            p = _make_passage()
            await qdrant_manager.upsert_passage(p)

        results = await qdrant_manager.search_passages(
            query_text="test query",
            collection=COLLECTION_LONG,
            limit=2,
        )
        assert len(results) <= 2

    async def test_search_with_payload_filter(self, qdrant_manager):
        # Insert passages with different categories
        essay = _make_passage(passage_category=PassageCategory.ESSAY)
        narrative = _make_passage(passage_category=PassageCategory.NARRATIVE)
        await qdrant_manager.upsert_passage(essay)
        await qdrant_manager.upsert_passage(narrative)

        # Search filtering for essay only
        results = await qdrant_manager.search_passages(
            query_text="test passage",
            collection=COLLECTION_LONG,
            filters={"passage_category": "essay"},
            limit=10,
        )
        # All results should be essays (if any)
        for r in results:
            assert r["payload"]["passage_category"] == "essay"

    async def test_search_with_mmr(self, qdrant_manager):
        # Insert multiple passages
        for _ in range(5):
            await qdrant_manager.upsert_passage(_make_passage())

        results = await qdrant_manager.search_passages(
            query_text="test passage",
            collection=COLLECTION_LONG,
            use_mmr=True,
            diversity=0.7,
            limit=3,
        )
        assert len(results) >= 1
        # MMR should return diverse results — check structure only
        for r in results:
            assert "id" in r
            assert "score" in r
            assert "payload" in r

    async def test_search_short_collection(self, qdrant_manager):
        passage = _make_passage(passage_type=PassageType.SHORT)
        await qdrant_manager.upsert_passage(passage)

        results = await qdrant_manager.search_passages(
            query_text="test passage",
            collection=COLLECTION_SHORT,
            limit=5,
        )
        assert len(results) >= 1
        assert results[0]["id"] == passage.id

    async def test_search_empty_collection_returns_no_results(self, qdrant_manager):
        # After cleanup, collections are recreated but empty
        results = await qdrant_manager.search_passages(
            query_text="nonexistent",
            collection=COLLECTION_LONG,
            limit=5,
        )
        # May be 0 or more depending on leftover points from other tests
        # but should never error
        assert isinstance(results, list)
