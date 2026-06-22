"""Bootstrap the library: fetch Gutenberg passages, process, embed, and upsert into Qdrant."""

from __future__ import annotations

import argparse
import asyncio

import structlog
from tqdm import tqdm

from backend.app.scraper.gutenberg import (
    fetch_catalogue,
    fetch_passage_text,
)
from backend.app.scraper.processor import chunk_text, process_raw_text
from backend.app.storage.qdrant import QdrantManager

from bootstrap.stats import StatsTracker

logger = structlog.get_logger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap passage library from Project Gutenberg",
    )
    parser.add_argument(
        "--max-books",
        type=int,
        default=200,
        help="Maximum number of books to process (default: 200)",
    )
    parser.add_argument(
        "--topics",
        type=str,
        default="science,history,philosophy,literature",
        help="Comma-separated search topics",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Qdrant upsert, only print stats",
    )
    args = parser.parse_args()

    topics = [t.strip() for t in args.topics.split(",")]
    stats = StatsTracker()

    if not args.dry_run:
        qdrant = QdrantManager()
        await qdrant.init_collections()
    else:
        qdrant = None
        logger.info("Dry-run mode — Qdrant upsert disabled")

    logger.info("Fetching catalogue", max_books=args.max_books, topics=topics)
    books = await fetch_catalogue(topics=topics, n=args.max_books)
    logger.info("Catalogue fetched", count=len(books))

    stats.total_books = len(books)

    for book in tqdm(books, desc="Processing books"):
        try:
            book_id = book["id"]
            title = book.get("title", "Unknown")
            source_url = book["formats"]["text/plain"]

            cleaned = await fetch_passage_text(book_id)
            chunks = chunk_text(cleaned)

            for chunk in chunks:
                try:
                    passage = process_raw_text(
                        chunk,
                        source_url=source_url,
                        source_title=title,
                    )
                    if qdrant:
                        await qdrant.upsert_passage(passage)
                    stats.record_passage(passage)
                except ValueError as exc:
                    logger.debug("Skipping unsuitable passage", error=str(exc))
                except Exception as exc:
                    logger.warning("Failed to process passage", error=str(exc))
                    stats.record_error()
        except Exception as exc:
            logger.warning(
                "Failed to process book",
                book_id=book.get("id"),
                error=str(exc),
            )
            stats.record_error()

    if qdrant:
        await qdrant.close()
    print()
    print(stats.report())


if __name__ == "__main__":
    asyncio.run(main())
