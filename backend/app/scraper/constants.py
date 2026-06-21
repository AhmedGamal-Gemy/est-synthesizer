"""EST Synthesizer — Scraper Constants.

All tunable values that do not belong in ``.env`` live here.
Values that operators may want to override per deployment are in
:mod:`backend.app.config`.
"""

from __future__ import annotations

import re

from backend.app.schemas import PassageCategory

# ═══════════════════════════════════════════════════════════════════════════════
#  Gutendex API URL templates
# ═══════════════════════════════════════════════════════════════════════════════

GUTENBERG_TEXT_PRIMARY_TEMPLATE: str = (
    "https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt"
)
GUTENBERG_TEXT_FALLBACK_TEMPLATE: str = (
    "https://www.gutenberg.org/ebooks/{book_id}.txt.utf-8"
)

# ═══════════════════════════════════════════════════════════════════════════════
#  Rate limiting
# ═══════════════════════════════════════════════════════════════════════════════

GUTENDEX_PAGE_DELAY: float = 0.25  # seconds between page fetches (free API)

# ═══════════════════════════════════════════════════════════════════════════════
#  Default search topics for catalogue discovery
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_SEARCH_TOPICS: list[str] = [
    "science",
    "history",
    "essay",
    "philosophy",
    "nature",
    "social",
    "politics",
    "economics",
    "literature",
    "psychology",
    "education",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  Subject / bookshelf exclusion filter (catalogue-level)
# ═══════════════════════════════════════════════════════════════════════════════

EXCLUDED_SUBJECT_KEYWORDS: set[str] = {
    "religion",
    "religious",
    "bible",
    "christian",
    "catholic",
    "protestant",
    "islam",
    "muslim",
    "quran",
    "koran",
    "theology",
    "gospel",
    "sermon",
    "salvation",
    "erotica",
    "pornography",
    "sex",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  Regex patterns for Gutenberg boilerplate stripping
# ═══════════════════════════════════════════════════════════════════════════════
# Primary markers: *** START OF (THE) PROJECT GUTENBERG EBOOK ... ***
# (THE is optional, space after *** is optional)

START_MARKER_PRIMARY: re.Pattern[str] = re.compile(
    r"\*\*\*\s?START OF (THE )?PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE | re.DOTALL,
)

END_MARKER_PRIMARY: re.Pattern[str] = re.compile(
    r"\*\*\*\s?END OF (THE )?PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE | re.DOTALL,
)

# Alternate no-space markers: ***START OF THE PROJECT GUTENBERG EBOOK***

START_MARKER_ALT: re.Pattern[str] = re.compile(
    r"\*\*\*START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE | re.DOTALL,
)

END_MARKER_ALT: re.Pattern[str] = re.compile(
    r"\*\*\*END OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE | re.DOTALL,
)

# ═══════════════════════════════════════════════════════════════════════════════
#  Passage chunking
# ═══════════════════════════════════════════════════════════════════════════════
# Full Gutenberg books are split into passage-sized chunks before processing.

SHORT_MIN_WORDS: int = 80
SHORT_MAX_WORDS: int = 250
LONG_MIN_WORDS: int = 250
LONG_MAX_WORDS: int = 600

# Target words per chunk when splitting a long book into passages.
# Chunks are formed at sentence boundaries near this target.
CHUNK_TARGET_WORDS: int = 300
# Number of overlapping sentences at chunk boundaries (0 = no overlap).
CHUNK_OVERLAP_SENTENCES: int = 0

# Threshold for classify_passage_type (between SHORT_MAX and LONG_MIN).
PASSAGE_TYPE_THRESHOLD: int = 250

# ═══════════════════════════════════════════════════════════════════════════════
#  Passage category keyword maps  (no‑LLM heuristic)
# ═══════════════════════════════════════════════════════════════════════════════
# Each category has a list of distinctive keywords.  The classifier counts
# whole-word matches and picks the highest-scoring category.

CATEGORY_KEYWORDS: dict[PassageCategory, list[str]] = {
    PassageCategory.SCIENTIFIC: [
        "experiment", "study", "data", "analysis", "scientific",
        "laboratory", "observed", "hypothesis", "theory", "species",
        "evolution", "chemical", "biological", "physics",
    ],
    PassageCategory.HISTORY: [
        "century", "ancient", "medieval", "empire", "civilization",
        "revolution", "war", "battle", "kingdom", "dynasty",
        "historical", "era", "reign", "colony", "parliament",
    ],
    PassageCategory.ARGUMENTATIVE: [
        "argue", "debate", "claim", "therefore", "thus",
        "consequently", "objection", "premise", "conclusion",
        "reasoning", "however", "nevertheless", "opposed", "assertion",
    ],
    PassageCategory.NARRATIVE: [
        "said", "walked", "told", "felt", "thought",
        "remember", "once upon", "story", "tale", "character",
        "journey", "adventure", "castle", "forest", "village",
    ],
    # ESSAY keywords are deliberately narrower to avoid false positives.
    PassageCategory.ESSAY: [
        "essay", "discourse", "treatise", "consideration",
        "remark", "opinion",
    ],
}

# Tiebreaker order: highest priority first when scores are equal.
CATEGORY_TIEBREAKER_ORDER: list[PassageCategory] = [
    PassageCategory.ESSAY,
    PassageCategory.NARRATIVE,
    PassageCategory.SCIENTIFIC,
    PassageCategory.HISTORY,
    PassageCategory.ARGUMENTATIVE,
]

# ═══════════════════════════════════════════════════════════════════════════════
#  Content suitability
# ═══════════════════════════════════════════════════════════════════════════════
# Keywords that make a passage text unsuitable for EST.
UNSUITABLE_CONTENT_KEYWORDS: list[str] = [
    "sexually",
    "pornographic",
    "erotica",
    "biblical",
    "scripture",
    "prayer",
    "christ",
    "allah",
    "prophet",
    "gospel",
    "divine",
    "worship",
    "quran",
    "deity",
    "sacred",
    "holy",
]
