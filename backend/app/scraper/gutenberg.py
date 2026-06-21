"""Gutendex API client for fetching passages from Project Gutenberg.

Provides three public async functions:

- :func:`fetch_catalogue` — query Gutendex for English books with content filtering.
- :func:`fetch_passage_text` — download and clean plain text for a given book ID.
- :func:`strip_gutenberg_boilerplate` — extract text between Gutenberg START / END markers.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from backend.app.config import settings
from backend.app.scraper.constants import (
    DEFAULT_SEARCH_TOPICS,
    END_MARKER_ALT,
    END_MARKER_PRIMARY,
    EXCLUDED_SUBJECT_KEYWORDS,
    GUTENBERG_TEXT_FALLBACK_TEMPLATE,
    GUTENBERG_TEXT_PRIMARY_TEMPLATE,
    GUTENDEX_PAGE_DELAY,
    START_MARKER_ALT,
    START_MARKER_PRIMARY,
)

logger = structlog.get_logger(__name__)

# ── Custom exception ─────────────────────────────────────────────────────────


class GutenbergFetchError(Exception):
    """Raised when a Gutenberg passage text download or marker parsing fails."""


# ── Public API ───────────────────────────────────────────────────────────────


async def fetch_catalogue(
    topics: list[str] | None = None,
    n: int | None = None,
) -> list[dict[str, Any]]:
    """Query Gutendex for English plain-text books, applying content filters.

    Searches each topic individually via Gutendex, collects unique book
    results, and filters out books with excluded subjects or very old authors.

    A small delay is inserted between page fetches to be a good citizen to
    the free Gutendex API.

    Args:
        topics: Optional list of topic keywords to search via Gutendex.
            Defaults to :data:`DEFAULT_SEARCH_TOPICS` when ``None``.
        n: Maximum number of unique books to return.
            Defaults to :attr:`settings.GUTENDEX_MAX_BOOKS` when ``None``.

    Returns:
        A list of dicts each containing: ``id``, ``title``, ``authors``,
        ``subjects``, ``formats`` (only ``text/plain; charset=utf-8`` URL).
    """
    if topics is None:
        topics = DEFAULT_SEARCH_TOPICS
    if n is None:
        n = settings.GUTENDEX_MAX_BOOKS

    seen_ids: set[int] = set()
    collected: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=settings.GUTENDEX_REQUEST_TIMEOUT, follow_redirects=True) as client:
        for topic in topics:
            if len(collected) >= n:
                logger.debug("Reached target of %d books, stopping topic loop", n)
                break

            url: str | None = (
                f"{settings.GUTENDEX_BASE_URL}"
                f"?languages=en&mime_type=text/plain&search={topic}"
            )

            while url and len(collected) < n:
                logger.info("Fetching Gutendex page", topic=topic)
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning(
                        "Gutendex request failed",
                        topic=topic,
                        error=str(exc),
                    )
                    break

                data = resp.json()

                for book in data.get("results", []):
                    book_id = book.get("id")
                    if book_id is None:
                        logger.debug("Skipping book with no id field")
                        continue
                    if book_id in seen_ids:
                        continue
                    if _is_excluded(book):
                        continue
                    entry = _extract_entry(book)
                    if entry is None:
                        continue

                    seen_ids.add(book_id)
                    collected.append(entry)
                    logger.debug("Collected book", book_id=book_id, title=entry.get("title"))
                    if len(collected) >= n:
                        break

                url = data.get("next")
                if url:
                    await asyncio.sleep(GUTENDEX_PAGE_DELAY)

    logger.info(
        "Collected books from Gutendex catalogue",
        count=len(collected),
        topics=len(topics),
    )
    return collected


async def fetch_passage_text(book_id: int) -> str:
    """Download plain text for a Gutenberg book and strip boilerplate.

    Tries the primary URL first; falls back to the alternate URL on failure.
    Raises :exc:`GutenbergFetchError` if the cleaned content is empty or
    boilerplate markers are missing.

    Args:
        book_id: Project Gutenberg numeric book ID.

    Returns:
        Cleaned passage text with Gutenberg boilerplate removed.

    Raises:
        GutenbergFetchError: If both primary and fallback URLs fail, or the
            cleaned text is empty / has no valid passage content.
    """
    primary = GUTENBERG_TEXT_PRIMARY_TEMPLATE.format(book_id=book_id)
    fallback = GUTENBERG_TEXT_FALLBACK_TEMPLATE.format(book_id=book_id)

    async with httpx.AsyncClient(timeout=settings.GUTENDEX_PASSAGE_TIMEOUT) as client:
        for label, url in (("primary", primary), ("fallback", fallback)):
            try:
                logger.info("Downloading passage", label=label, url=url)
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                raw_text = resp.text
                cleaned = strip_gutenberg_boilerplate(raw_text)
                if not cleaned.strip():
                    logger.warning(
                        "Cleaned text is empty",
                        book_id=book_id,
                        label=label,
                    )
                    continue
                logger.info(
                    "Successfully downloaded book",
                    book_id=book_id,
                    label=label,
                    chars=len(cleaned),
                )
                return cleaned
            except httpx.HTTPError as exc:
                logger.warning(
                    "Failed to fetch URL",
                    label=label,
                    url=url,
                    error=str(exc),
                )
                continue
            except GutenbergFetchError:
                logger.warning(
                    "Boilerplate parsing failed",
                    label=label,
                    book_id=book_id,
                )
                continue

    raise GutenbergFetchError(
        f"Could not download text for Gutenberg book {book_id}",
    )


def strip_gutenberg_boilerplate(text: str) -> str:
    """Extract passage text between Gutenberg START / END markers.

    Both markers must be present and start/end must occur in the expected
    order.  Partial or absent markers raise :exc:`GutenbergFetchError`.

    Args:
        text: Raw plain text from a Gutenberg file.

    Returns:
        Stripped passage content between the markers.

    Raises:
        GutenbergFetchError: If both START and END markers cannot be located.
    """
    # Try primary markers (with optional THE and optional space)
    start_match = START_MARKER_PRIMARY.search(text)
    end_match = END_MARKER_PRIMARY.search(text)

    # Fallback: try alternate no-space markers
    if not start_match:
        start_match = START_MARKER_ALT.search(text)
    if not end_match:
        end_match = END_MARKER_ALT.search(text)

    if start_match and end_match:
        content = text[start_match.end() : end_match.start()]
        logger.debug("Stripped Gutenberg boilerplate", chars=len(content))
        return content.strip()

    if start_match:
        logger.error("END marker missing — cannot safely extract passage content")
        raise GutenbergFetchError("END marker not found (partial Gutenberg file)")

    if end_match:
        logger.error("START marker missing — cannot safely extract passage content")
        raise GutenbergFetchError("START marker not found (partial Gutenberg file)")

    logger.error("No Gutenberg START/END markers found")
    raise GutenbergFetchError("No Gutenberg START/END markers found in text")


# ── Internal helpers ─────────────────────────────────────────────────────────


def _is_excluded(book: dict[str, Any]) -> bool:
    """Return ``True`` if the book should be filtered out of the catalogue.

    Checks whether any subject or bookshelf *contains* an excluded keyword
    as a substring, and whether the earliest author's birth year is below
    the configured threshold.
    """
    all_subjects: list[str] = book.get("subjects", []) + book.get("bookshelves", [])
    for subject in all_subjects:
        subject_lower = subject.lower()
        for excluded in EXCLUDED_SUBJECT_KEYWORDS:
            if excluded in subject_lower:
                logger.debug(
                    "Excluding book by subject",
                    book_id=book.get("id"),
                    subject=subject_lower,
                    keyword=excluded,
                )
                return True

    authors = book.get("authors", [])
    birth_years = [
        a.get("birth_year") for a in authors if a.get("birth_year") is not None
    ]
    if birth_years and min(birth_years) < settings.GUTENDEX_MIN_AUTHOR_BIRTH_YEAR:
        logger.debug(
            "Excluding book by author birth year",
            book_id=book.get("id"),
            birth_year=min(birth_years),
            threshold=settings.GUTENDEX_MIN_AUTHOR_BIRTH_YEAR,
        )
        return True

    return False


def _extract_entry(book: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a catalogue entry dict from a Gutendex book record.

    Returns ``None`` if no ``text/plain`` format URL (UTF-8 or US-ASCII)
    is available.
    """
    formats = book.get("formats", {})
    text_url = formats.get(
        "text/plain; charset=utf-8",
    ) or formats.get("text/plain; charset=us-ascii")
    if not text_url:
        logger.debug(
            "Skipping book — no text/plain format URL",
            book_id=book.get("id"),
        )
        return None

    return {
        "id": book.get("id"),
        "title": book.get("title", ""),
        "authors": book.get("authors", []),
        "subjects": book.get("subjects", []),
        "formats": {"text/plain": text_url},
    }
