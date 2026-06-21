"""Unit tests for backend.app.scraper.gutenberg — mocked HTTP."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from backend.app.scraper.gutenberg import (
    GutenbergFetchError,
    _extract_entry,
    _is_excluded,
    fetch_catalogue,
    fetch_passage_text,
    strip_gutenberg_boilerplate,
)


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
        authors = [{"name": "John Smith", "birth_year": 1850}]
    if subjects is None:
        subjects = ["Science"]
    if bookshelves is None:
        bookshelves = []
    if formats is None:
        formats = {"text/plain; charset=utf-8": f"https://www.gutenberg.org/files/{id}/{id}-0.txt"}
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


# ── _is_excluded ──────────────────────────────────────────────────────────────


def test_is_excluded_rejects_religion_subject():
    book = _gutendex_book(subjects=["Religion"])
    assert _is_excluded(book) is True


def test_is_excluded_rejects_erotica_bookshelf():
    book = _gutendex_book(bookshelves=["Erotica"])
    assert _is_excluded(book) is True


def test_is_excluded_rejects_pre1700_author():
    book = _gutendex_book(authors=[{"name": "Ancient Writer", "birth_year": 400}])
    assert _is_excluded(book) is True


def test_is_excluded_accepts_normal_book():
    book = _gutendex_book()
    assert _is_excluded(book) is False


def test_is_excluded_rejects_sex_substring_in_subject():
    book = _gutendex_book(subjects=["Sex education"])
    assert _is_excluded(book) is True


def test_is_excluded_rejects_bible_subject():
    book = _gutendex_book(subjects=["Bible study"])
    assert _is_excluded(book) is True


# ── _extract_entry ────────────────────────────────────────────────────────────


def test_extract_entry_returns_dict_with_utf8_format():
    book = _gutendex_book(id=84, title="Frankenstein")
    entry = _extract_entry(book)
    assert entry is not None
    assert entry["id"] == 84
    assert entry["title"] == "Frankenstein"
    assert entry["formats"]["text/plain"] == f"https://www.gutenberg.org/files/84/84-0.txt"


def test_extract_entry_accepts_us_ascii_format():
    """Fallback to text/plain; charset=us-ascii when UTF-8 is absent."""
    book = _gutendex_book(
        id=99,
        formats={"text/plain; charset=us-ascii": "https://example.com/99.txt"},
    )
    entry = _extract_entry(book)
    assert entry is not None
    assert entry["id"] == 99
    assert entry["formats"]["text/plain"] == "https://example.com/99.txt"


def test_extract_entry_returns_none_without_utf8_format():
    book = _gutendex_book(formats={"text/html": "https://example.com/book.html"})
    entry = _extract_entry(book)
    assert entry is None


def test_extract_entry_preserves_authors_and_subjects():
    book = _gutendex_book(
        authors=[{"name": "Mary Shelley", "birth_year": 1797}],
        subjects=["Gothic fiction", "Science fiction"],
    )
    entry = _extract_entry(book)
    assert entry["authors"] == [{"name": "Mary Shelley", "birth_year": 1797}]
    assert entry["subjects"] == ["Gothic fiction", "Science fiction"]


# ── strip_gutenberg_boilerplate ───────────────────────────────────────────────


def test_boilerplate_strips_with_THE_markers():
    text = (
        "Header junk\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK FRANKENSTEIN ***\n"
        "Actual content here.\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK FRANKENSTEIN ***\n"
        "Footer junk"
    )
    result = strip_gutenberg_boilerplate(text)
    assert result == "Actual content here."


def test_boilerplate_strips_without_THE_markers():
    text = (
        "Header junk\n"
        "*** START OF PROJECT GUTENBERG EBOOK FRANKENSTEIN ***\n"
        "Actual content here.\n"
        "*** END OF PROJECT GUTENBERG EBOOK FRANKENSTEIN ***\n"
        "Footer junk"
    )
    result = strip_gutenberg_boilerplate(text)
    assert result == "Actual content here."


def test_boilerplate_raises_error_when_no_markers():
    text = "Just some plain text without any Gutenberg markers."
    with pytest.raises(GutenbergFetchError, match="No Gutenberg START/END markers found"):
        strip_gutenberg_boilerplate(text)


def test_boilerplate_handles_alt_no_space_markers():
    text = (
        "Header junk\n"
        "***START OF THE PROJECT GUTENBERG EBOOK FRANKENSTEIN***\n"
        "Actual content here.\n"
        "***END OF THE PROJECT GUTENBERG EBOOK FRANKENSTEIN***\n"
        "Footer junk"
    )
    result = strip_gutenberg_boilerplate(text)
    assert result == "Actual content here."


# ── fetch_catalogue (async, mocked httpx) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_catalogue_returns_books_with_correct_structure():
    book = _gutendex_book(id=84, title="Frankenstein")
    page = _gutendex_page(results=[book], next=None)

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = page
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        # We need AsyncClient to support the async context manager protocol
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        results = await fetch_catalogue(topics=["science"], n=200)

    assert len(results) == 1
    assert results[0]["id"] == 84
    assert results[0]["title"] == "Frankenstein"


@pytest.mark.asyncio
async def test_fetch_catalogue_filters_excluded_subjects():
    book_religion = _gutendex_book(id=10, subjects=["Religion"])
    book_normal = _gutendex_book(id=84, subjects=["Science"])
    page = _gutendex_page(results=[book_religion, book_normal], next=None)

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = page
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        results = await fetch_catalogue(topics=["science"], n=200)

    assert len(results) == 1
    assert results[0]["id"] == 84


@pytest.mark.asyncio
async def test_fetch_catalogue_filters_pre1700_authors():
    book_old = _gutendex_book(id=20, authors=[{"name": "Plato", "birth_year": -428}])
    book_new = _gutendex_book(id=84, authors=[{"name": "Mary Shelley", "birth_year": 1797}])
    page = _gutendex_page(results=[book_old, book_new], next=None)

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = page
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        results = await fetch_catalogue(topics=["science"], n=200)

    assert len(results) == 1
    assert results[0]["id"] == 84


@pytest.mark.asyncio
async def test_fetch_catalogue_deduplicates_across_topics():
    book = _gutendex_book(id=84, title="Frankenstein")
    page = _gutendex_page(results=[book], next=None)

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = page
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        # Two topics return same book — should deduplicate
        results = await fetch_catalogue(topics=["science", "philosophy"], n=200)

    # Same book appears only once
    assert len(results) == 1
    assert results[0]["id"] == 84


@pytest.mark.asyncio
async def test_fetch_catalogue_only_keeps_utf8_format():
    book_no_utf8 = _gutendex_book(
        id=99,
        formats={"text/html": "https://example.com/99.html"},
    )
    book_utf8 = _gutendex_book(id=84)
    page = _gutendex_page(results=[book_no_utf8, book_utf8], next=None)

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = page
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        results = await fetch_catalogue(topics=["science"], n=200)

    assert len(results) == 1
    assert results[0]["id"] == 84


@pytest.mark.asyncio
async def test_fetch_catalogue_handles_pagination():
    book1 = _gutendex_book(id=84, title="Book 1")
    book2 = _gutendex_book(id=100, title="Book 2")
    page1 = _gutendex_page(results=[book1], next="https://gutendex.com/books?page=2")
    page2 = _gutendex_page(results=[book2], next=None)

    mock_client = AsyncMock()
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = page1
    mock_resp1.raise_for_status = MagicMock()
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = page2
    mock_resp2.raise_for_status = MagicMock()

    # First call returns page1, second returns page2
    mock_client.get = AsyncMock(side_effect=[mock_resp1, mock_resp2])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        results = await fetch_catalogue(topics=["science"], n=200)

    assert len(results) == 2
    assert results[0]["id"] == 84
    assert results[1]["id"] == 100


@pytest.mark.asyncio
async def test_fetch_catalogue_handles_http_error_gracefully():
    """HTTP error on a topic breaks that topic's loop but returns partial results."""
    book = _gutendex_book(id=84)
    page = _gutendex_page(results=[book], next=None)

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = page
    mock_response.raise_for_status = MagicMock()
    # First topic succeeds, second topic raises HTTPError
    mock_client.get = AsyncMock(
        side_effect=[mock_response, httpx.HTTPError("Connection failed")]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        results = await fetch_catalogue(topics=["science", "philosophy"], n=200)

    # Only got book from first successful topic
    assert len(results) == 1
    assert results[0]["id"] == 84


# ── fetch_passage_text (async, mocked httpx) ──────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_passage_text_downloads_and_strips_boilerplate():
    raw_text = (
        "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
        "This is the passage content.\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
    )

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.text = raw_text
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_passage_text(book_id=84)

    assert result == "This is the passage content."


@pytest.mark.asyncio
async def test_fetch_passage_text_falls_back_on_primary_failure():
    raw_text = (
        "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
        "Fallback content.\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
    )

    mock_client = AsyncMock()
    mock_primary_resp = MagicMock()
    mock_primary_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPError("Primary failed")
    )
    mock_fallback_resp = MagicMock()
    mock_fallback_resp.text = raw_text
    mock_fallback_resp.raise_for_status = MagicMock()
    # Primary fails, fallback succeeds
    mock_client.get = AsyncMock(
        side_effect=[mock_primary_resp, mock_fallback_resp]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_passage_text(book_id=84)

    assert result == "Fallback content."


@pytest.mark.asyncio
async def test_fetch_passage_text_raises_error_when_both_urls_fail():
    mock_client = AsyncMock()
    mock_resp1 = MagicMock()
    mock_resp1.raise_for_status = MagicMock(
        side_effect=httpx.HTTPError("Primary failed")
    )
    mock_resp2 = MagicMock()
    mock_resp2.raise_for_status = MagicMock(
        side_effect=httpx.HTTPError("Fallback failed")
    )
    mock_client.get = AsyncMock(side_effect=[mock_resp1, mock_resp2])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.scraper.gutenberg.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(GutenbergFetchError):
            await fetch_passage_text(book_id=84)
