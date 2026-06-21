"""EST Synthesizer - Qdrant vector storage & search.

Provides an async ``QdrantManager`` that:
- Creates / reuses ``long_passages`` and ``short_passages`` collections
- Embeds passages via local sentence-transformers (BGE) model
- Searches with cosine similarity and optional MMR diversity
"""

from __future__ import annotations

import asyncio
import structlog
from typing import Any

from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    Mmr,
    NearestQuery,
    PayloadSchemaType,
    PointStruct,
    Range,
    VectorParams,
)

from backend.app.config import settings
from backend.app.schemas import Passage

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLLECTION_LONG = settings.QDRANT_COLLECTION_LONG
COLLECTION_SHORT = settings.QDRANT_COLLECTION_SHORT
COLLECTIONS = (COLLECTION_LONG, COLLECTION_SHORT)

EMBEDDING_MODEL_NAME = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
VECTOR_SIZE = getattr(settings, "EMBEDDING_VECTOR_SIZE", 1024)
QUERY_PREFIX = getattr(settings, "EMBEDDING_QUERY_PREFIX", "Represent this sentence for searching relevant passages: ")

# Lazy-loaded sentence-transformers singleton (downloaded on first use)
_embedding_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    """Return the shared SentenceTransformer instance (lazy init)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model", model=EMBEDDING_MODEL_NAME)
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded", dim=_embedding_model.get_sentence_embedding_dimension())
    return _embedding_model

# MMR defaults (used when use_mmr=True but no explicit values given)
MMR_DEFAULT_DIVERSITY = 0.5
MMR_DEFAULT_CANDIDATES = 100

# Payload fields indexed for filtering (field → schema type)
PAYLOAD_INDEXES: dict[str, PayloadSchemaType] = {
    "passage_type": PayloadSchemaType.KEYWORD,
    "reading_level": PayloadSchemaType.FLOAT,
    "word_count": PayloadSchemaType.INTEGER,
    "last_used_at": PayloadSchemaType.KEYWORD,
}

# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class QdrantManager:
    """Async wrapper around Qdrant for passage storage and retrieval."""

    def __init__(self, url: str = settings.QDRANT_URL) -> None:
        self.client: AsyncQdrantClient = AsyncQdrantClient(
            url=url,
            # qdrant-client 1.18.x vs server 1.15.x — minor diff > 1
            # triggers a warning and silently drops operations.
            # Suppress the check so real upserts/searches work.
            check_compatibility=False,
        )

    # ── lifecycle ────────────────────────────────────────

    async def init_collections(self) -> None:
        """Create collections + payload indexes if they don't exist."""
        for name in COLLECTIONS:
            exists = await self.client.collection_exists(name)
            if exists:
                logger.info("Collection already exists, skipping", collection=name)
                continue

            try:
                await self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=VECTOR_SIZE,
                        distance=Distance.COSINE,
                    ),
                )
            except Exception as exc:
                # Qdrant may reject creation if stale on-disk data remains
                # from a prior run — collection_exists returns False while
                # data files block a fresh creation. Force-recreate to clear
                # the zombie state.
                if "already exists" in str(exc).lower():
                    logger.warning(
                        "Collection has stale on-disk data, deleting and recreating",
                        collection=name,
                    )
                    await self.client.delete_collection(name)
                    await self.client.create_collection(
                        collection_name=name,
                        vectors_config=VectorParams(
                            size=VECTOR_SIZE,
                            distance=Distance.COSINE,
                        ),
                    )
                else:
                    raise

            logger.info(
                "Created collection",
                collection=name,
                vector_size=VECTOR_SIZE,
                distance="COSINE",
            )

            for field, schema_type in PAYLOAD_INDEXES.items():
                await self.client.create_payload_index(
                    collection_name=name,
                    field_name=field,
                    field_schema=schema_type,
                )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.close()
        logger.info("Qdrant client closed.")

    # ── embedding ────────────────────────────────────────

    async def _embed(self, text: str, *, is_query: bool = False) -> list[float]:
        """Return a dense vector for *text* via the local BGE model.

        BGE models require an instruction prefix for *query* texts but not
        for *document* texts.  ``is_query=True`` prepends the configured
        ``QUERY_PREFIX``; ``is_query=False`` (the default, used for
        upserts) embeds the raw text.

        ``SentenceTransformer.encode()`` is synchronous so we offload it
        to a thread via ``asyncio.to_thread()``.
        """
        input_text = (QUERY_PREFIX + text) if is_query else text
        model = _get_embedding_model()
        vector: list[float] = await asyncio.to_thread(
            model.encode, input_text, convert_to_numpy=False,
        )
        return vector

    # ── write ────────────────────────────────────────────

    async def upsert_passage(self, passage: Passage) -> None:
        """Store a passage (with its embedding) in the matching Qdrant collection.

        The collection is chosen by ``passage.passage_type.value``
        (``"long"`` → ``long_passages``, ``"short"`` → ``short_passages``).
        """
        collection = (
            COLLECTION_LONG
            if passage.passage_type.value == "long"
            else COLLECTION_SHORT
        )
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
                    passage.last_used_at.isoformat()
                    if passage.last_used_at
                    else None
                ),
            },
        )

        await self.client.upsert(collection_name=collection, points=[point])
        logger.debug(
            "Upserted passage",
            passage_id=passage.id,
            passage_type=passage.passage_type.value,
            word_count=passage.word_count,
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
        diversity: float | None = None,
        candidates_limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search *collection* by cosine similarity to *query_text*.

        Uses Qdrant's ``query_points`` API which natively supports MMR
        (requires Qdrant server >= 1.15.0).

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
            Maximum number of results to return.
        use_mmr:
            Enable diversity-aware re-ranking via MMR.
        diversity:
            MMR diversity (0.0 = pure relevance, 1.0 = max diversity).
            Defaults to 0.5 when *use_mmr* is True.
        candidates_limit:
            Number of candidates to pre-select before MMR re-rank.
            Defaults to 100 when *use_mmr* is True.

        Returns
        -------
        List of ``{id, score, payload}`` dicts.
        """
        query_vector = await self._embed(query_text, is_query=True)
        qdrant_filter = _build_filter(filters) if filters else None

        if use_mmr:
            query = NearestQuery(
                nearest=query_vector,
                mmr=Mmr(
                    diversity=diversity if diversity is not None else MMR_DEFAULT_DIVERSITY,
                    candidates_limit=candidates_limit or MMR_DEFAULT_CANDIDATES,
                ),
            )
        else:
            query = NearestQuery(nearest=query_vector)

        hits = await self.client.query_points(
            collection_name=collection,
            query=query,
            query_filter=qdrant_filter,
            limit=limit,
        )

        return [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload,
            }
            for point in hits.points
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
