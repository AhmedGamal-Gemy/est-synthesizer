"""
EST Synthesizer — Passage Processing Pipeline
===============================================

Transforms raw Project Gutenberg text into validated
:class:`~backend.app.schemas.passage.Passage` objects ready for Qdrant storage.
"""

from __future__ import annotations

import re
import uuid
from typing import Iterator

import structlog
import textstat

from backend.app.schemas import Passage, PassageCategory, PassageType
from backend.app.scraper.constants import (
    CATEGORY_KEYWORDS,
    CATEGORY_TIEBREAKER_ORDER,
    CHUNK_TARGET_WORDS,
    LONG_MAX_WORDS,
    LONG_MIN_WORDS,
    PASSAGE_TYPE_THRESHOLD,
    SHORT_MAX_WORDS,
    SHORT_MIN_WORDS,
    UNSUITABLE_CONTENT_KEYWORDS,
)

logger = structlog.get_logger(__name__)


# ── Chunking ─────────────────────────────────────────────────────────────────


def chunk_text(text: str, target_words: int = CHUNK_TARGET_WORDS) -> list[str]:
    """Split *text* into sentence-aligned chunks of roughly *target_words*.

    Uses a greedy sentence-accumulation strategy: collect sentences until
    the accumulated word count reaches *target_words*, then yield the chunk
    and start a new one.  Final chunk may be shorter.

    Args:
        text: Long raw text to split (typically a full Gutenberg book).
        target_words: Desired word count per chunk.

    Returns:
        List of chunk strings, each roughly *target_words* long.
    """
    if not text.strip():
        return []

    # Split on sentence boundaries (., !, ?) followed by whitespace.
    # Note: this may also split on abbreviations (Mr., Dr., etc.), but
    # that is acceptable for chunking purposes — the resulting chunks
    # will still be valid passages with slightly shifted boundaries.
    sentence_end = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_end.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())
        # If this single sentence already exceeds target, push it as its own chunk.
        if sentence_words >= target_words:
            if current:
                chunks.append(" ".join(current))
            chunks.append(sentence)
            current = []
            current_words = 0
            continue

        if current_words > 0 and current_words + sentence_words > target_words:
            chunks.append(" ".join(current))
            current = [sentence]
            current_words = sentence_words
        else:
            current.append(sentence)
            current_words += sentence_words

    if current:
        chunks.append(" ".join(current))

    logger.debug(
        "Chunked text",
        total_words=sum(len(c.split()) for c in chunks),
        chunks=len(chunks),
        target=target_words,
    )
    return chunks


# ── Reading level ────────────────────────────────────────────────────────────


def compute_reading_level(text: str) -> float:
    """Compute Flesch-Kincaid grade level for *text*, rounded to 1 decimal.

    Returns 0.0 for empty or whitespace-only input.
    """
    if not text.strip():
        logger.debug("Reading level: empty text, returning 0.0")
        return 0.0
    score = textstat.flesch_kincaid_grade(text)
    result = round(score, 1)
    logger.debug("Reading level computed", score=round(score, 4), rounded=result)
    return result


# ── Type classification ─────────────────────────────────────────────────────


def classify_passage_type(text: str, word_count: int | None = None) -> PassageType:
    """Classify a passage as LONG or SHORT by word count.

    Threshold is :data:`PASSAGE_TYPE_THRESHOLD` (250 words).

    Uses *word_count* if provided; otherwise counts from *text*.
    """
    if word_count is None:
        word_count = len(text.split())
    passage_type = PassageType.LONG if word_count > PASSAGE_TYPE_THRESHOLD else PassageType.SHORT
    logger.debug("Classified passage type", word_count=word_count, passage_type=passage_type.value)
    return passage_type


# ── Category classification (keyword heuristic, no LLM) ─────────────────────


def classify_passage_category(text: str) -> PassageCategory:
    """Classify passage content category via keyword heuristic (no LLM).

    Scores each category by counting case-insensitive whole-word keyword
    occurrences.  Returns the highest-scoring category with tiebreaker
    applied.  Defaults to :attr:`PassageCategory.ESSAY` when no keywords
    match.
    """
    lower_text = text.lower()
    word_set = set(re.findall(r"[a-z]+", lower_text))

    scores: dict[PassageCategory, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        count = 0
        for kw in keywords:
            kw_lower = kw.lower()
            if " " in kw_lower:
                if kw_lower in lower_text:
                    count += 1
            else:
                if kw_lower in word_set:
                    count += 1
        scores[category] = count

    max_score = max(scores.values())
    logger.debug("Category keyword scores", scores={k.name: v for k, v in scores.items()})

    if max_score == 0:
        logger.debug("No keywords matched, defaulting to ESSAY")
        return PassageCategory.ESSAY

    tied = [cat for cat, s in scores.items() if s == max_score]
    for tiebreaker_cat in CATEGORY_TIEBREAKER_ORDER:
        if tiebreaker_cat in tied:
            logger.debug(
                "Category chosen by tiebreaker",
                max_score=max_score,
                category=tiebreaker_cat.value,
            )
            return tiebreaker_cat

    return tied[0]


# ── Suitability check ───────────────────────────────────────────────────────


def is_suitable(reading_level: float, word_count: int, text: str) -> bool:
    """Return ``True`` only if the passage meets all suitability criteria:

    - Reading level between 8.0 and 14.0 (inclusive)
    - Word count between :data:`SHORT_MIN_WORDS` and :data:`LONG_MAX_WORDS`
    - Text does not contain unsuitable content keywords
    """
    if not (8.0 <= reading_level <= 14.0):
        logger.debug(
            "Suitability rejected: reading level out of range",
            reading_level=reading_level,
        )
        return False
    if not (SHORT_MIN_WORDS <= word_count <= LONG_MAX_WORDS):
        logger.debug(
            "Suitability rejected: word count out of range",
            word_count=word_count,
            min_words=SHORT_MIN_WORDS,
            max_words=LONG_MAX_WORDS,
        )
        return False
    lower_text = text.lower()
    for kw in UNSUITABLE_CONTENT_KEYWORDS:
        if kw in lower_text:
            logger.debug(
                "Suitability rejected: unsuitable keyword found",
                keyword=kw,
            )
            return False
    logger.debug(
        "Suitability accepted",
        reading_level=reading_level,
        word_count=word_count,
    )
    return True


# ── Full pipeline ────────────────────────────────────────────────────────────


def process_raw_text(raw_text: str, source_url: str, source_title: str) -> Passage:
    """Orchestrate the full processing pipeline on raw scraped text.

    Steps:
      1. Count words
      2. Classify passage type (LONG / SHORT)
      3. Compute reading level
      4. Check suitability — raise :exc:`ValueError` if unsuitable
      5. Classify passage category
      6. Generate UUID4
      7. Construct and return :class:`~backend.app.schemas.passage.Passage` object

    Embedding is **not** set here — that is handled separately by the
    orchestrator (expensive model load).
    """
    word_count = len(raw_text.split())
    logger.debug("Processing raw text", word_count=word_count, source=source_title)

    passage_type = classify_passage_type(raw_text, word_count)
    reading_level = compute_reading_level(raw_text)

    if not is_suitable(reading_level, word_count, raw_text):
        raise ValueError(
            f"Passage not suitable: reading_level={reading_level}, "
            f"word_count={word_count}, source='{source_title}'",
        )

    passage_category = classify_passage_category(raw_text)
    passage_id = str(uuid.uuid4())

    passage = Passage(
        id=passage_id,
        text=raw_text,
        source_url=source_url,
        source_title=source_title,
        passage_type=passage_type,
        passage_category=passage_category,
        word_count=word_count,
        reading_level=reading_level,
    )

    logger.info(
        "Processed passage %s: type=%s, category=%s, words=%d, rl=%.1f",
        passage_id,
        passage_type.value,
        passage_category.value,
        word_count,
        reading_level,
    )

    return passage
