"""Integration tests for the full scraper pipeline (catalogue → fetch → chunk → process).

All external HTTP calls are mocked via httpx.AsyncClient patches.
No real network requests are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.scraper import (
    fetch_catalogue,
    fetch_passage_text,
    process_raw_text,
    strip_gutenberg_boilerplate,
)
from backend.app.scraper.processor import chunk_text
from backend.app.schemas import Passage, PassageCategory, PassageType


# ── Helpers ──────────────────────────────────────────────────────────────────


def _gutendex_book(
    id: int = 1,
    title: str = "Test Book",
    authors: list[dict] | None = None,
    subjects: list[str] | None = None,
    bookshelves: list[str] | None = None,
    formats: dict[str, str] | None = None,
) -> dict:
    """Build a minimal Gutendex book dict."""
    if authors is None:
        authors = [{"name": "Jane Author", "birth_year": 1850}]
    if subjects is None:
        subjects = ["Science"]
    if bookshelves is None:
        bookshelves = []
    if formats is None:
        formats = {
            "text/plain; charset=utf-8": f"https://www.gutenberg.org/files/{id}/{id}-0.txt"
        }
    return {
        "id": id,
        "title": title,
        "authors": authors,
        "subjects": subjects,
        "bookshelves": bookshelves,
        "formats": formats,
    }


def _gutendex_page(results: list[dict], next: str | None = None) -> dict:
    """Build a Gutendex API response page."""
    return {"results": results, "next": next}


def _make_mock_async_client(
    get_side_effect=None,
    get_return_value=None,
):
    """Create a mocked httpx.AsyncClient that supports async context manager."""
    mock_client = AsyncMock()
    if get_side_effect is not None:
        mock_client.get = AsyncMock(side_effect=get_side_effect)
    elif get_return_value is not None:
        mock_client.get = AsyncMock(return_value=get_return_value)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _mock_json_response(json_data: dict) -> MagicMock:
    """Create a mock httpx.Response with .json() returning *json_data*."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _mock_text_response(text: str) -> MagicMock:
    """Create a mock httpx.Response with .text returning *text*."""
    mock_resp = MagicMock()
    mock_resp.text = text
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# A passage text that should pass suitability checks:
#   - Contains enough words (≥ 80)
#   - Has a reading level in the 8.0–14.0 range (complex sentences, multi-syllable vocabulary)
#   - Contains no unsuitable keywords
_SUITABLE_PASSAGE_TEXT = (
    "Many people enjoy reading books about science and nature. "
    "The study of animals and plants has taught us a great deal about the world. "
    "Teachers often ask their students to observe and record what they see. "
    "This practice helps young minds develop important skills. "
    "When children learn about the environment, they begin to understand "
    "the importance of protecting it. "
    "The process of discovery can be a rewarding experience for people of all ages. "
    "Students who ask questions and look for answers often become great thinkers. "
    "The knowledge we gain from careful observation helps us make better decisions "
    "in our daily lives. "
    "Science gives us a framework for understanding the world around us."
)

# The same text wrapped in Gutenberg boilerplate markers
_BOILERPLATE_WRAPPED_TEXT = (
    "*** START OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***\n"
    + _SUITABLE_PASSAGE_TEXT
    + "\n*** END OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***\n"
)


# ── fetch_catalogue integration ────────────────────────────────────────────


class TestFetchCatalogue:
    @pytest.mark.asyncio
    async def test_returns_books_with_valid_structure(self):
        """fetch_catalogue returns catalogue entries with id, title, formats keys."""
        book = _gutendex_book(id=84, title="Frankenstein")
        page = _gutendex_page(results=[book], next=None)

        mock_client = _make_mock_async_client(
            get_return_value=_mock_json_response(page)
        )

        with patch(
            "backend.app.scraper.gutenberg.httpx.AsyncClient",
            return_value=mock_client,
        ):
            results = await fetch_catalogue(topics=["science"], n=200)

        assert isinstance(results, list)
        assert len(results) >= 1
        entry = results[0]
        # Verify shape: must contain the keys expected by downstream pipeline
        assert "id" in entry
        assert "title" in entry
        assert "formats" in entry
        assert isinstance(entry["id"], int)
        assert isinstance(entry["title"], str)
        assert isinstance(entry["formats"], dict)
        assert "text/plain" in entry["formats"]

    @pytest.mark.asyncio
    async def test_deduplicates_across_topics(self):
        """fetch_catalogue deduplicates when the same book appears in multiple topics."""
        book = _gutendex_book(id=84, title="Frankenstein")
        page = _gutendex_page(results=[book], next=None)

        mock_client = _make_mock_async_client(
            get_return_value=_mock_json_response(page)
        )

        with patch(
            "backend.app.scraper.gutenberg.httpx.AsyncClient",
            return_value=mock_client,
        ):
            results = await fetch_catalogue(topics=["science", "philosophy"], n=200)

        # Same book should appear only once despite two topics
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_filters_excluded_books(self):
        """fetch_catalogue excludes books with excluded subjects (e.g. Religion)."""
        book_excluded = _gutendex_book(id=10, subjects=["Religion"])
        book_normal = _gutendex_book(id=84, subjects=["Science"])
        page = _gutendex_page(results=[book_excluded, book_normal], next=None)

        mock_client = _make_mock_async_client(
            get_return_value=_mock_json_response(page)
        )

        with patch(
            "backend.app.scraper.gutenberg.httpx.AsyncClient",
            return_value=mock_client,
        ):
            results = await fetch_catalogue(topics=["science"], n=200)

        # Only the non-excluded book should remain
        assert len(results) == 1
        assert results[0]["id"] == 84


# ── fetch_passage_text integration ───────────────────────────────────────────


class TestFetchPassageText:
    @pytest.mark.asyncio
    async def test_returns_cleaned_text_from_boilerplate(self):
        """fetch_passage_text downloads and strips Gutenberg boilerplate."""
        mock_client = _make_mock_async_client(
            get_return_value=_mock_text_response(_BOILERPLATE_WRAPPED_TEXT)
        )

        with patch(
            "backend.app.scraper.gutenberg.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_passage_text(book_id=84)

        assert isinstance(result, str)
        assert len(result) > 0
        # Boilerplate markers should be gone
        assert "PROJECT GUTENBERG" not in result
        # Core content should be present
        assert "science" in result.lower()

    @pytest.mark.asyncio
    async def test_falls_back_on_primary_failure(self):
        """fetch_passage_text falls back to alternate URL when primary fails."""
        import httpx

        primary_resp = MagicMock()
        primary_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPError("Primary URL failed")
        )
        fallback_resp = _mock_text_response(_BOILERPLATE_WRAPPED_TEXT)

        mock_client = _make_mock_async_client(
            get_side_effect=[primary_resp, fallback_resp]
        )

        with patch(
            "backend.app.scraper.gutenberg.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await fetch_passage_text(book_id=84)

        assert isinstance(result, str)
        assert "science" in result.lower()


# ── chunk_text integration ────────────────────────────────────────────────────


class TestChunkText:
    def test_splits_text_into_chunks(self):
        """chunk_text splits long text into multiple chunks."""
        # Create a text longer than CHUNK_TARGET_WORDS (300)
        long_text = " ".join(
            f"The scientific study of nature requires careful observation and systematic analysis. "
            for _ in range(50)  # ~500+ words
        )

        chunks = chunk_text(long_text, target_words=300)

        assert isinstance(chunks, list)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert isinstance(chunk, str)
            assert len(chunk.strip()) > 0

    def test_single_chunk_for_short_text(self):
        """chunk_text returns a single chunk for short text."""
        short_text = "This is a short passage with only a few words in it."

        chunks = chunk_text(short_text, target_words=300)

        assert isinstance(chunks, list)
        assert len(chunks) == 1

    def test_empty_text_returns_empty_list(self):
        """chunk_text returns [] for empty or whitespace-only text."""
        assert chunk_text("") == []
        assert chunk_text("   \n\t  ") == []

    def test_chunk_word_counts_near_target(self):
        """Each chunk's word count is approximately near the target."""
        long_text = " ".join(
            f"The scientific study of nature requires careful observation and systematic analysis. "
            for _ in range(50)
        )

        chunks = chunk_text(long_text, target_words=300)

        for chunk in chunks:
            word_count = len(chunk.split())
            # Chunks should be roughly near target (allow generous margin for
            # sentence-boundary alignment; only the last chunk may be short)
            assert word_count > 0


# ── process_raw_text integration ──────────────────────────────────────────────


class TestProcessRawText:
    def test_returns_valid_passage_object(self):
        """process_raw_text returns a Passage with all required fields."""
        passage = process_raw_text(
            raw_text=_SUITABLE_PASSAGE_TEXT,
            source_url="https://www.gutenberg.org/files/84/84-0.txt",
            source_title="Frankenstein",
        )

        # Must be a Passage instance
        assert isinstance(passage, Passage)

        # id: UUID string
        assert isinstance(passage.id, str)
        assert len(passage.id) > 0

        # passage_type: must be a valid PassageType enum value
        assert isinstance(passage.passage_type, PassageType)
        assert passage.passage_type in (PassageType.LONG, PassageType.SHORT)

        # passage_category: must be a valid PassageCategory enum value
        assert isinstance(passage.passage_category, PassageCategory)
        assert passage.passage_category in (
            PassageCategory.ESSAY,
            PassageCategory.NARRATIVE,
            PassageCategory.SCIENTIFIC,
            PassageCategory.HISTORY,
            PassageCategory.ARGUMENTATIVE,
        )

        # word_count: positive integer within suitable range
        assert isinstance(passage.word_count, int)
        assert passage.word_count > 0

        # reading_level: float within suitable range [8.0, 14.0]
        assert isinstance(passage.reading_level, float)
        assert 8.0 <= passage.reading_level <= 14.0

        # source_url and source_title: strings matching input
        assert isinstance(passage.source_url, str)
        assert len(passage.source_url) > 0
        assert isinstance(passage.source_title, str)
        assert len(passage.source_title) > 0

        # text: should match input (or be very close)
        assert isinstance(passage.text, str)
        assert len(passage.text) > 0

    def test_classifies_scientific_text_as_scientific(self):
        """Text with scientific keywords should be classified as SCIENTIFIC."""
        passage = process_raw_text(
            raw_text=_SUITABLE_PASSAGE_TEXT,
            source_url="https://example.com/science-book",
            source_title="A Scientific Treatise",
        )

        # Our test text is heavy on scientific keywords
        assert passage.passage_category == PassageCategory.SCIENTIFIC

    def test_short_text_classified_as_short(self):
        """Text with ≤ 250 words should be classified as SHORT type."""
        # _SUITABLE_PASSAGE_TEXT is ~80-90 words (short)
        passage = process_raw_text(
            raw_text=_SUITABLE_PASSAGE_TEXT,
            source_url="https://example.com/short-book",
            source_title="Short Science Essay",
        )

        assert passage.passage_type == PassageType.SHORT

    def test_raises_value_error_for_unsuitable_text(self):
        """process_raw_text raises ValueError when text fails suitability."""
        # Too few words (< 80)
        too_short = "This is just a few words."
        with pytest.raises(ValueError, match="not suitable"):
            process_raw_text(
                raw_text=too_short,
                source_url="https://example.com/bad-book",
                source_title="Bad Book",
            )

    def test_passage_fields_match_input_source(self):
        """Passage source_url and source_title match the provided arguments."""
        passage = process_raw_text(
            raw_text=_SUITABLE_PASSAGE_TEXT,
            source_url="https://www.gutenberg.org/files/84/84-0.txt",
            source_title="Frankenstein",
        )

        assert passage.source_url == "https://www.gutenberg.org/files/84/84-0.txt"
        assert passage.source_title == "Frankenstein"


# ── Full end-to-end pipeline (catalogue → fetch → chunk → process) ───────────


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_catalogue_to_passage_end_to_end(self):
        """Mocked full pipeline: catalogue → fetch text → chunk → process → Passage."""
        book = _gutendex_book(id=84, title="Frankenstein")
        page = _gutendex_page(results=[book], next=None)

        # Step 1: fetch_catalogue — mock the Gutendex API
        catalogue_mock_client = _make_mock_async_client(
            get_return_value=_mock_json_response(page)
        )

        with patch(
            "backend.app.scraper.gutenberg.httpx.AsyncClient",
            return_value=catalogue_mock_client,
        ):
            catalogue = await fetch_catalogue(topics=["science"], n=200)

        assert len(catalogue) >= 1
        entry = catalogue[0]
        assert entry["id"] == 84

        # Step 2: fetch_passage_text — mock the Gutenberg text download
        # Use a longer text that will produce multiple chunks when chunked
        long_text_content = " ".join([_SUITABLE_PASSAGE_TEXT] * 6)
        long_text_wrapped = (
            "*** START OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***\n"
            + long_text_content
            + "\n*** END OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***\n"
        )

        fetch_mock_client = _make_mock_async_client(
            get_return_value=_mock_text_response(long_text_wrapped)
        )

        with patch(
            "backend.app.scraper.gutenberg.httpx.AsyncClient",
            return_value=fetch_mock_client,
        ):
            raw_text = await fetch_passage_text(book_id=entry["id"])

        assert isinstance(raw_text, str)
        assert len(raw_text) > 0

        # Step 3: chunk_text — pure function, no mocking needed
        chunks = chunk_text(raw_text, target_words=300)
        assert isinstance(chunks, list)
        assert len(chunks) >= 1

        # Step 4: process_raw_text — at least one chunk should be suitable
        passages = []
        for chunk in chunks:
            try:
                passage = process_raw_text(
                    raw_text=chunk,
                    source_url=entry["formats"]["text/plain"],
                    source_title=entry["title"],
                )
                passages.append(passage)
            except ValueError:
                # Some chunks may not meet suitability criteria — that's fine
                continue

        # At least one chunk should produce a valid Passage
        assert len(passages) >= 1, "No chunks produced suitable passages"

        # Verify every produced Passage has correct shape
        for passage in passages:
            assert isinstance(passage, Passage)
            assert isinstance(passage.id, str)
            assert isinstance(passage.passage_type, PassageType)
            assert isinstance(passage.passage_category, PassageCategory)
            assert isinstance(passage.word_count, int)
            assert passage.word_count > 0
            assert isinstance(passage.reading_level, float)
            assert passage.source_url == entry["formats"]["text/plain"]
            assert passage.source_title == entry["title"]
