"""EST Synthesizer - Scraper API endpoints for manual testing."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query

from backend.app.config import settings
from backend.app.scraper import (
    GutenbergFetchError,
    fetch_catalogue,
    fetch_passage_text,
)
from backend.app.scraper.constants import CHUNK_TARGET_WORDS
from backend.app.scraper.processor import chunk_text, process_raw_text

router = APIRouter(prefix="/api/scraper", tags=["scraper"])
logger = structlog.get_logger(__name__)


# ── GET /api/scraper/catalogue ───────────────────────────────────────────────


@router.get("/catalogue")
async def catalogue(
    topics: str | None = Query(
        default=None,
        description="Comma-separated topic keywords (defaults to DEFAULT_SEARCH_TOPICS)",
    ),
    max_books: int | None = Query(
        default=None,
        description="Maximum number of books to return (defaults to GUTENDEX_MAX_BOOKS)",
    ),
):
    """Fetch the Gutendex catalogue filtered by topics and max_books."""
    topic_list: list[str] | None = None
    if topics is not None:
        topic_list = [t.strip() for t in topics.split(",") if t.strip()]

    n = max_books if max_books is not None else settings.GUTENDEX_MAX_BOOKS

    logger.info("Catalogue fetch requested", topics=topic_list, max_books=n)

    try:
        books = await fetch_catalogue(topics=topic_list, n=n)
    except GutenbergFetchError as exc:
        logger.error("Catalogue fetch failed", error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc))

    logger.info("Catalogue fetch completed", count=len(books))
    return {"count": len(books), "books": books}


# ── GET /api/scraper/book/{book_id} ─────────────────────────────────────────


@router.get("/book/{book_id}")
async def book_detail(book_id: int):
    """Download and process a single Gutenberg book by ID."""
    logger.info("Book download requested", book_id=book_id)

    # Step 1: Download text
    try:
        text = await fetch_passage_text(book_id)
    except GutenbergFetchError as exc:
        logger.error("Book download failed", book_id=book_id, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc))

    logger.info("Book downloaded", book_id=book_id, chars=len(text))

    # Step 2: Chunk
    chunks = chunk_text(text, target_words=CHUNK_TARGET_WORDS)
    logger.info("Text chunked", book_id=book_id, chunk_count=len(chunks))

    # Step 3: Process each chunk
    source_url = f"https://www.gutenberg.org/ebooks/{book_id}"
    source_title = f"Gutenberg Book {book_id}"

    passages: list[dict[str, Any]] = []
    skipped: int = 0

    for idx, chunk in enumerate(chunks):
        try:
            passage = process_raw_text(chunk, source_url=source_url, source_title=source_title)
            passages.append(passage.model_dump(mode="json"))
            logger.info(
                "Passage processed",
                book_id=book_id,
                chunk_index=idx,
                passage_id=passage.id,
                passage_type=passage.passage_type.value,
                word_count=passage.word_count,
                reading_level=passage.reading_level,
            )
        except ValueError as exc:
            skipped += 1
            logger.warning(
                "Chunk skipped (unsuitable)",
                book_id=book_id,
                chunk_index=idx,
                reason=str(exc),
            )

    logger.info(
        "Book processing completed",
        book_id=book_id,
        total_chunks=len(chunks),
        passages=len(passages),
        skipped=skipped,
    )

    return {
        "book_id": book_id,
        "source_url": source_url,
        "source_title": source_title,
        "total_chunks": len(chunks),
        "passages": passages,
        "skipped_chunks": skipped,
    }


# ── GET /api/scraper/pipeline ───────────────────────────────────────────────


@router.get("/pipeline")
async def pipeline(
    max_books: int = Query(default=3, description="Number of books to process from catalogue"),
    topics: str | None = Query(
        default=None,
        description="Comma-separated topic keywords (defaults to DEFAULT_SEARCH_TOPICS)",
    ),
):
    """Full pipeline: catalogue → pick first N books → download + process each."""
    topic_list: list[str] | None = None
    if topics is not None:
        topic_list = [t.strip() for t in topics.split(",") if t.strip()]

    logger.info("Pipeline requested", max_books=max_books, topics=topic_list)

    # Step 1: Fetch catalogue
    try:
        books = await fetch_catalogue(topics=topic_list, n=max_books)
    except GutenbergFetchError as exc:
        logger.error("Pipeline catalogue fetch failed", error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc))

    logger.info("Pipeline catalogue fetched", book_count=len(books))

    # Step 2: Process each book
    results: list[dict[str, Any]] = []
    total_passages: int = 0
    total_skipped: int = 0

    for book in books:
        book_id = book.get("id")
        source_url = book.get("formats", {}).get("text/plain", "")
        source_title = book.get("title", f"Gutenberg Book {book_id}")

        logger.info("Pipeline processing book", book_id=book_id, title=source_title)

        try:
            text = await fetch_passage_text(book_id)
        except GutenbergFetchError as exc:
            logger.warning(
                "Pipeline: book download failed, skipping",
                book_id=book_id,
                error=str(exc),
            )
            results.append({
                "book_id": book_id,
                "title": source_title,
                "status": "failed",
                "error": str(exc),
                "passages": [],
                "passage_count": 0,
                "skipped_chunks": 0,
            })
            continue

        chunks = chunk_text(text, target_words=CHUNK_TARGET_WORDS)
        logger.info(
            "Pipeline: text chunked",
            book_id=book_id,
            chunk_count=len(chunks),
        )

        passages: list[dict[str, Any]] = []
        skipped: int = 0

        for idx, chunk in enumerate(chunks):
            try:
                passage = process_raw_text(
                    chunk,
                    source_url=source_url,
                    source_title=source_title,
                )
                passages.append(passage.model_dump(mode="json"))
                logger.info(
                    "Pipeline: passage processed",
                    book_id=book_id,
                    chunk_index=idx,
                    passage_id=passage.id,
                )
            except ValueError:
                skipped += 1
                logger.debug(
                    "Pipeline: chunk skipped",
                    book_id=book_id,
                    chunk_index=idx,
                )

        total_passages += len(passages)
        total_skipped += skipped

        results.append({
            "book_id": book_id,
            "title": source_title,
            "status": "ok",
            "total_chunks": len(chunks),
            "passages": passages,
            "passage_count": len(passages),
            "skipped_chunks": skipped,
        })

    logger.info(
        "Pipeline completed",
        books_processed=len(results),
        total_passages=total_passages,
        total_skipped=total_skipped,
    )

    return {
        "books_requested": max_books,
        "books_processed": len(results),
        "total_passages": total_passages,
        "total_skipped_chunks": total_skipped,
        "results": results,
    }
