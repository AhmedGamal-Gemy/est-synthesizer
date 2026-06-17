"""Debug script for Qdrant UUID retrieval issue."""
import asyncio
from unittest.mock import AsyncMock

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from backend.app.config import settings
from backend.app.schemas import Passage, PassageCategory, PassageType
from backend.app.storage.qdrant import (
    COLLECTION_LONG,
    EMBEDDING_MODEL_NAME,
    PAYLOAD_INDEXES,
    QdrantManager,
    VECTOR_SIZE,
)

DUMMY_VECTOR = [0.1] * 1024


async def test_direct_upsert():
    """Test with raw client, check_compatibility=False."""
    client = AsyncQdrantClient(url=settings.QDRANT_URL, check_compatibility=False)

    # Clean slate
    try:
        await client.delete_collection(COLLECTION_LONG)
    except Exception:
        pass
    await asyncio.sleep(0.5)

    # Create collection + indexes
    await client.create_collection(
        collection_name=COLLECTION_LONG,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    for field, schema_type in PAYLOAD_INDEXES.items():
        await client.create_payload_index(
            collection_name=COLLECTION_LONG,
            field_name=field,
            field_schema=schema_type,
        )

    # Upsert directly
    uid = str(__import__("uuid").uuid4())
    point = PointStruct(
        id=uid,
        vector=DUMMY_VECTOR,
        payload={
            "text": "Direct upsert test",
            "source_url": "https://example.com",
            "source_title": "Direct Test",
            "passage_type": "long",
            "passage_category": "essay",
            "word_count": 500,
            "reading_level": 10.0,
            "last_used_at": None,
        },
    )
    result = await client.upsert(collection_name=COLLECTION_LONG, points=[point])
    print(f"Upsert result: {result} (status={result.status})")

    await asyncio.sleep(1.0)

    # Check via scroll
    records, _ = await client.scroll(collection_name=COLLECTION_LONG, limit=10)
    print(f"Scroll: {len(records)} points")
    for r in records:
        print(f"  id={r.id} (type={type(r.id).__name__})")

    # Check via retrieve
    pts = await client.retrieve(collection_name=COLLECTION_LONG, ids=[uid])
    print(f"Retrieve: {len(pts)} points")

    await client.delete_collection(COLLECTION_LONG)
    await client.close()


async def test_manager_upsert():
    """Test with QdrantManager + mocked _embed + check_compatibility=False."""
    manager = QdrantManager(url=settings.QDRANT_URL)

    # Override client to skip version compatibility check
    # (client 1.18.0 vs server 1.15.0 — minor version diff > 1)
    await manager.client.close()
    manager.client = AsyncQdrantClient(
        url=settings.QDRANT_URL, check_compatibility=False
    )

    manager._embed = AsyncMock(return_value=DUMMY_VECTOR)

    # init_collections will create/reuse collections
    await manager.init_collections()

    passage = Passage(
        id=str(__import__("uuid").uuid4()),
        text="Manager upsert test",
        source_url="https://example.com",
        source_title="Manager Test",
        passage_type=PassageType.LONG,
        passage_category=PassageCategory.ESSAY,
        word_count=500,
        reading_level=10.0,
    )

    await manager.upsert_passage(passage)
    print(f"_embed called: {manager._embed.called}, count={manager._embed.call_count}")

    await asyncio.sleep(1.0)

    # Check via scroll
    records, _ = await manager.client.scroll(
        collection_name=COLLECTION_LONG, limit=10
    )
    print(f"Manager scroll: {len(records)} points")
    for r in records:
        print(f"  id={r.id} (type={type(r.id).__name__})")

    # Check via retrieve
    pts = await manager.client.retrieve(
        collection_name=COLLECTION_LONG, ids=[passage.id]
    )
    print(f"Manager retrieve: {len(pts)} points")

    # Cleanup
    await manager.client.delete_collection(COLLECTION_LONG)
    await manager.close()


async def main():
    print("=" * 60)
    print("TEST 1: Direct client upsert (check_compatibility=False)")
    print("=" * 60)
    await test_direct_upsert()

    print()
    print("=" * 60)
    print("TEST 2: QdrantManager upsert")
    print("=" * 60)
    await test_manager_upsert()


if __name__ == "__main__":
    asyncio.run(main())
