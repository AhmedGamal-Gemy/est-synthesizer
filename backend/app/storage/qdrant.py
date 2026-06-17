"""EST Synthesizer - Qdrant vector storage & search.

Provides an async ``QdrantManager`` that:
- Creates / reuses ``long_passages`` and ``short_passages`` collections
- Embeds passages via LiteLLM and upserts them
- Searches by cosine similarity with optional payload filters
"""

from __future__ import annotations

import logging
from typing import Any

import litellm
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from backend.app.config import settings
from backend.app.schemas import Passage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLLECTION_LONG = settings.QDRANT_COLLECTION_LONG
COLLECTION_SHORT = settings.QDRANT_COLLECTION_SHORT
COLLECTIONS = (COLLECTION_LONG, COLLECTION_SHORT)

EMBEDDING_MODEL = getattr(settings, "EMBEDDING_MODEL", "mistral/mistral-embed")
VECTOR_SIZE = getattr(settings, "EMBEDDING_VECTOR_SIZE", 1024)

# Payload fields indexed for filtering
PAYLOAD_INDEXES = [
    "passage_type",
    "reading_level",
    "word_count",
    "last_used_at",
]

# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class QdrantManager:
    """Async wrapper around Qdrant for passage storage and retrieval."""

    def __init__(self, url: str = settings.QDRANT_URL) -> None:
        self.client: AsyncQdrantClient = AsyncQdrantClient(url=url)

    # ── lifecycle ────────────────────────────────────────

    async def init_collections(self) -> None:
        """Create collections + payload indexes if they don't exist."""
        for name in COLLECTIONS:
            exists = await self.client.collection_exists(name)
            if exists:
                logger.info("Collection '%s' already exists, skipping.", name)
                continue

            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created collection '%s' (size=%d, distance=COSINE).", name, VECTOR_SIZE)

            # Payload indexes for filtered search
            for field in PAYLOAD_INDEXES:
                await self.client.create_payload_index(
                    collection_name=name,
                    field_name=field,
                )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.close()
        logger.info("Qdrant client closed.")

    # ── embedding ────────────────────────────────────────

    async def _embed(self, text: str) -> list[float]:
        """Return a dense vector for *text* via LiteLLM."""
        resp = await litellm.aembedding(model=EMBEDDING_MODEL, input=text)
        return resp.data[0]["embedding"]  # type: ignore[index]

    # ── write ────────────────────────────────────────────

    async def upsert_passage(self, passage: Passage) -> None:
        """Store a passage (with its embedding) in the matching Qdrant collection.

        The collection is chosen by ``passage.passage_type.value``
        (``"long"`` → ``long_passages``, ``"short"`` → ``short_passages``).
        """
        collection = COLLECTION_LONG if passage.passage_type.value == "long" else COLLECTION_SHORT
        vector = await self._embed(passage.text)

        point = PointStruct(
            id=passage.id,
            vector=vector,
            payload={
                "text": passage.text,
                "source_url": passage.source_url,
                "source_title": passage.source_title,
                "passage_type": passage.passage_type.value,
                "passage_category": passage.passage_category.value,
                "word_count": passage.word_count,
                "reading_level": passage.reading_level,
                "last_used_at": (
                    passage.last_used_at.isoformat() if passage.last_used_at else None
                ),
            },
        )

        await self.client.upsert(collection_name=collection, points=[point])
        logger.debug(
            "Upserted passage '%s' (%s, %d words).",
            passage.id,
            passage.passage_type.value,
            passage.word_count,
        )

    # ── read ─────────────────────────────────────────────

    async def search_passages(
        self,
        query_text: str,
        collection: str = COLLECTION_LONG,
        filters: dict[str, Any] | None = None,
        limit: int = 5,
        *,
        use_mmr: bool = False,
    ) -> list[dict[str, Any]]:
        """Search *collection* by cosine similarity to *query_text*.

        Parameters
        ----------
        query_text:
            Natural-language query to embed.
        collection:
            One of ``long_passages`` or ``short_passages``.
        filters:
            Optional payload filters, e.g. ``{"passage_category": "essay"}``
            or ``{"reading_level": {"gte": 8, "lte": 14}}``.
        limit:
            Maximum number of results.
        use_mmr:
            Not yet supported — raises ``NotImplementedError``.

        Returns
        -------
        List of ``{id, score, payload}`` dicts.
        """
        if use_mmr:
            raise NotImplementedError("MMR search is post-MVP")

        query_vector = await self._embed(query_text)

        qdrant_filter = _build_filter(filters) if filters else None

        hits = await self.client.search(
            collection_name=collection,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in hits
        ]


# ── filter builder ────────────────────────────────────────


def _build_filter(filters: dict[str, Any]) -> Filter:
    """Convert a plain dict into a Qdrant ``Filter``.

    Supported operators per field:
    - Exact match: ``{"field": value}``
    - Range: ``{"field": {"gte": …, "lte": …}}``
    """
    conditions: list[FieldCondition] = []
    for field, value in filters.items():
        if isinstance(value, dict):
            conditions.append(
                FieldCondition(
                    key=field,
                    range=Range(
                        gte=value.get("gte"),
                        lte=value.get("lte"),
                    ),
                )
            )
        else:
            conditions.append(
                FieldCondition(
                    key=field,
                    match=MatchValue(value=value),
                )
            )
    return Filter(must=conditions)
