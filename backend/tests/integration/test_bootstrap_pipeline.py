"""Integration tests for the bootstrap pipeline — mocked Gutenberg, real Qdrant."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.bootstrap.stats import StatsTracker
from scripts.bootstrap_library import main


def _gutendex_book(id: int = 84, title: str = "Test") -> dict:
    return {
        "id": id,
        "title": title,
        "authors": [{"name": "Author", "birth_year": 1800}],
        "subjects": ["Science"],
        "formats": {"text/plain": f"https://example.com/{id}.txt"},
    }


def _gutenberg_text(word_count: int = 300) -> str:
    words = "word " * word_count
    return (
        "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
        f"{words}\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
    )


@pytest.mark.asyncio
async def test_bootstrap_pipeline_full_flow():
    """Full pipeline: catalogue → fetch → process → upsert."""
    books = [_gutendex_book(id=84, title="Frankenstein")]
    raw_text = _gutenberg_text(300)

    mock_qdrant = AsyncMock()
    mock_qdrant.init_collections = AsyncMock()
    mock_qdrant.close = AsyncMock()
    mock_qdrant.upsert_passage = AsyncMock()

    with (
        patch("scripts.bootstrap_library.QdrantManager", return_value=mock_qdrant),
        patch("scripts.bootstrap_library.fetch_catalogue", new_callable=AsyncMock, return_value=books),
        patch("scripts.bootstrap_library.fetch_passage_text", new_callable=AsyncMock, return_value=raw_text),
        patch("scripts.bootstrap_library.chunk_text", return_value=[raw_text]),
        patch("scripts.bootstrap_library.process_raw_text") as mock_process,
        patch.object(sys, "argv", ["bootstrap_library.py"]),
    ):
        from backend.app.schemas.enums import PassageCategory, PassageType
        mock_passage = MagicMock(spec_set=[
            "source_url", "passage_type", "passage_category", "reading_level",
        ])
        mock_passage.source_url = "https://example.com/84.txt"
        mock_passage.passage_type = PassageType.LONG
        mock_passage.passage_category = PassageCategory.SCIENTIFIC
        mock_passage.reading_level = 9.5
        mock_process.return_value = mock_passage
        await main()

    # Verify flow
    mock_qdrant.init_collections.assert_awaited_once()
    assert mock_qdrant.upsert_passage.await_count >= 1
    mock_qdrant.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_bootstrap_pipeline_dry_run_skips_qdrant():
    """Dry-run should skip all Qdrant operations."""
    books = [_gutendex_book(id=84)]
    raw_text = _gutenberg_text(300)

    with (
        patch("scripts.bootstrap_library.fetch_catalogue", new_callable=AsyncMock, return_value=books),
        patch("scripts.bootstrap_library.fetch_passage_text", new_callable=AsyncMock, return_value=raw_text),
        patch("scripts.bootstrap_library.QdrantManager") as mock_qdrant_cls,
        patch.object(sys, "argv", ["bootstrap_library.py", "--dry-run"]),
    ):
        await main()

    # QdrantManager should NOT have been instantiated
    mock_qdrant_cls.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_pipeline_handles_unsuitable_passages():
    """Passages that fail suitability should not crash the pipeline."""
    books = [_gutendex_book(id=84)]
    raw_text = _gutenberg_text(50)

    mock_qdrant = AsyncMock()
    mock_qdrant.init_collections = AsyncMock()
    mock_qdrant.close = AsyncMock()
    mock_qdrant.upsert_passage = AsyncMock()

    with (
        patch("scripts.bootstrap_library.QdrantManager", return_value=mock_qdrant),
        patch("scripts.bootstrap_library.fetch_catalogue", new_callable=AsyncMock, return_value=books),
        patch("scripts.bootstrap_library.fetch_passage_text", new_callable=AsyncMock, return_value=raw_text),
        patch("scripts.bootstrap_library.chunk_text", return_value=[raw_text]),
        # process_raw_text raises ValueError for unsuitable text
        patch("scripts.bootstrap_library.process_raw_text",
              side_effect=ValueError("Passage not suitable")),
        patch.object(sys, "argv", ["bootstrap_library.py"]),
    ):
        await main()

    # The loop still completes without error
    mock_qdrant.close.assert_awaited_once()
    assert mock_qdrant.upsert_passage.await_count == 0


@pytest.mark.asyncio
async def test_bootstrap_pipeline_multiple_books():
    """Multiple books all get processed and upserted."""
    books = [_gutendex_book(id=84), _gutendex_book(id=100, title="Book Two")]
    raw_text = _gutenberg_text(300)

    mock_qdrant = AsyncMock()
    mock_qdrant.init_collections = AsyncMock()
    mock_qdrant.close = AsyncMock()
    mock_qdrant.upsert_passage = AsyncMock()

    with (
        patch("scripts.bootstrap_library.QdrantManager", return_value=mock_qdrant),
        patch("scripts.bootstrap_library.fetch_catalogue", new_callable=AsyncMock, return_value=books),
        patch("scripts.bootstrap_library.fetch_passage_text", new_callable=AsyncMock, return_value=raw_text),
        patch("scripts.bootstrap_library.chunk_text", return_value=[raw_text, raw_text]),
        patch("scripts.bootstrap_library.process_raw_text") as mock_process,
        patch.object(sys, "argv", ["bootstrap_library.py"]),
    ):
        from backend.app.schemas.enums import PassageCategory, PassageType
        _call_idx = 0
        _urls = ["https://example.com/84.txt", "https://example.com/100.txt"]

        def make_passage(*_a, **_kw):
            nonlocal _call_idx
            m = MagicMock(spec_set=[
                "source_url", "passage_type", "passage_category", "reading_level",
            ])
            m.source_url = _urls[_call_idx % len(_urls)]
            _call_idx += 1
            m.passage_type = PassageType.LONG
            m.passage_category = PassageCategory.SCIENTIFIC
            m.reading_level = 9.5
            return m
        mock_process.side_effect = make_passage
        await main()

    # Both books processed — each produces 2 chunks → 4 upserts
    assert mock_qdrant.upsert_passage.await_count == 4


@pytest.mark.asyncio
async def test_bootstrap_pipeline_multiple_chunks_per_book():
    """Multiple chunks from one book are all upserted."""
    book = {
        "id": 84,
        "title": "Dupe",
        "authors": [{"name": "Author", "birth_year": 1800}],
        "subjects": ["Science"],
        "formats": {"text/plain": "https://example.com/84.txt"},
    }
    # Long text → multiple chunks from the same source_url
    raw_text = _gutenberg_text(1200)

    mock_qdrant = AsyncMock()
    mock_qdrant.init_collections = AsyncMock()
    mock_qdrant.close = AsyncMock()
    mock_qdrant.upsert_passage = AsyncMock()

    from backend.app.schemas.enums import PassageCategory, PassageType

    def make_passage(*_a, **_kw):
        m = MagicMock(spec_set=[
            "source_url", "passage_type", "passage_category", "reading_level",
        ])
        m.source_url = "https://example.com/84.txt"
        m.passage_type = PassageType.LONG
        m.passage_category = PassageCategory.SCIENTIFIC
        m.reading_level = 9.5
        return m

    with (
        patch("scripts.bootstrap_library.QdrantManager", return_value=mock_qdrant),
        patch("scripts.bootstrap_library.fetch_catalogue", new_callable=AsyncMock, return_value=[book]),
        patch("scripts.bootstrap_library.fetch_passage_text", new_callable=AsyncMock, return_value=raw_text),
        patch("scripts.bootstrap_library.chunk_text",
              return_value=["chunk1", "chunk2", "chunk3"]),
        patch("scripts.bootstrap_library.process_raw_text",
              side_effect=make_passage),
        patch.object(sys, "argv", ["bootstrap_library.py"]),
    ):
        await main()

    # Multiple chunks from the same book → multiple upserts (no dedup)
    assert mock_qdrant.upsert_passage.await_count == 3
    mock_qdrant.close.assert_awaited_once()

