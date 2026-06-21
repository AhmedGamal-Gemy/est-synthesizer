"""EST Synthesizer — Scraper Package.

Provides passage scraping from Project Gutenberg and text processing.
"""

from __future__ import annotations

from backend.app.scraper.gutenberg import (
    GutenbergFetchError,
    fetch_catalogue,
    fetch_passage_text,
    strip_gutenberg_boilerplate,
)
from backend.app.scraper.processor import (
    classify_passage_category,
    classify_passage_type,
    compute_reading_level,
    is_suitable,
    process_raw_text,
)

__all__ = [
    "classify_passage_category",
    "classify_passage_type",
    "compute_reading_level",
    "fetch_catalogue",
    "fetch_passage_text",
    "GutenbergFetchError",
    "is_suitable",
    "process_raw_text",
    "strip_gutenberg_boilerplate",
]
