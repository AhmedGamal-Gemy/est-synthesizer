"""CRUD + visualize Qdrant passage collections.

Usage:
    uv run python scripts/qdrant_tool.py stats
    uv run python scripts/qdrant_tool.py list --limit 20
    uv run python scripts/qdrant_tool.py get <passage-id>
    uv run python scripts/qdrant_tool.py search "climate change" --limit 5
    uv run python scripts/qdrant_tool.py delete <passage-id>
    uv run python scripts/qdrant_tool.py collections
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import textwrap

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from backend.app.config import settings

logger = structlog.get_logger(__name__)

COLLECTION_LONG = settings.QDRANT_COLLECTION_LONG
COLLECTION_SHORT = settings.QDRANT_COLLECTION_SHORT
COLLECTIONS = (COLLECTION_LONG, COLLECTION_SHORT)


# ── helpers ──────────────────────────────────────────────────────────────────


async def _get_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.QDRANT_URL, check_compatibility=False)


def _fmt(payload: dict) -> str:
    """Format a passage payload for display, truncating long text."""
    text = payload.get("text", "")
    if len(text) > 120:
        text = text[:117] + "..."
    return text


def _print_table(rows: list[list[str]], headers: list[str]) -> None:
    """Print a left-aligned table with columns sized to content."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    sep = "-" * (sum(col_widths) + 3 * len(headers) - 1)
    header = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(f"  {header}")
    print(f"  {sep}")
    for row in rows:
        line = " | ".join(c.ljust(w) for c, w in zip(row, col_widths))
        print(f"  {line}")


def _parse_filters(filters_str: str | None) -> Filter | None:
    """Convert a JSON string like '{"passage_category": "essay"}' into a Qdrant Filter."""
    if not filters_str:
        return None
    try:
        raw = json.loads(filters_str)
    except json.JSONDecodeError as exc:
        print(f"  Invalid --filters JSON: {exc}")
        print(f"  Use double quotes inside, e.g. --filters '{{\"key\": \"value\"}}'")
        sys.exit(1)
    conditions: list[FieldCondition] = []
    for field, value in raw.items():
        if isinstance(value, dict):
            conditions.append(
                FieldCondition(key=field, range=Range(
                    gte=value.get("gte"),
                    lte=value.get("lte"),
                ))
            )
        else:
            conditions.append(
                FieldCondition(key=field, match=MatchValue(value=value))
            )
    return Filter(must=conditions) if conditions else None


# ── subcommands ──────────────────────────────────────────────────────────────


async def cmd_collections() -> None:
    """List all collections with point count and vector config."""
    client = await _get_client()
    rows = []
    for name in COLLECTIONS:
        exists = await client.collection_exists(name)
        if not exists:
            rows.append([name, "—", "—", "—"])
            continue
        info = await client.get_collection(name)
        count_result = await client.count(name)
        vec_config = info.config.params.vectors
        rows.append([
            name,
            str(count_result.count),
            f"{vec_config.size}d",
            vec_config.distance.name,
        ])
    await client.close()

    print()
    _print_table(rows, ["Collection", "Points", "Vector", "Distance"])
    print()


async def cmd_list(collection: str, limit: int, offset: int) -> None:
    """Scroll through passages in a collection."""
    client = await _get_client()
    if not await client.collection_exists(collection):
        print(f"  Collection '{collection}' does not exist.")
        await client.close()
        return

    hits, next_offset = await client.scroll(
        collection_name=collection,
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False,
    )

    rows = []
    for pt in hits:
        p = pt.payload or {}
        rows.append([
            pt.id[:12],
            p.get("passage_type", "-"),
            p.get("passage_category", "-"),
            str(p.get("word_count", "-")),
            str(p.get("reading_level", "-")),
            p.get("source_title", "-")[:40],
        ])

    print(f"\n  Collection: {collection}  |  Showing {len(rows)} passages")
    print()
    _print_table(rows, ["ID", "Type", "Category", "Words", "RL", "Source"])
    print()

    if next_offset is not None:
        print(f"  Next offset: {next_offset}  (use --offset {next_offset} to continue)")
    else:
        print(f"  All passages shown.")
    print()

    await client.close()


async def cmd_get(passage_id: str, collection: str) -> None:
    """Retrieve a single passage by ID."""
    client = await _get_client()
    if not await client.collection_exists(collection):
        print(f"  Collection '{collection}' does not exist.")
        await client.close()
        return

    hits = await client.retrieve(
        collection_name=collection,
        ids=[passage_id],
        with_payload=True,
        with_vectors=False,
    )

    if not hits:
        print(f"  No passage found with ID '{passage_id}' in '{collection}'.")
        # try the other collection
        other = COLLECTION_SHORT if collection == COLLECTION_LONG else COLLECTION_LONG
        hits = await client.retrieve(
            collection_name=other,
            ids=[passage_id],
            with_payload=True,
            with_vectors=False,
        )
        if hits:
            print(f"  Found in '{other}' instead:")
            collection = other

    if not hits:
        print(f"  No passage found with ID '{passage_id}' in either collection.")
        await client.close()
        return

    pt = hits[0]
    p = pt.payload or {}
    print(f"\n  {'=' * 60}")
    print(f"  Passage: {pt.id}")
    print(f"  {'=' * 60}")
    print(f"  Collection   : {collection}")
    print(f"  Type         : {p.get('passage_type', '-')}")
    print(f"  Category     : {p.get('passage_category', '-')}")
    print(f"  Word count   : {p.get('word_count', '-')}")
    print(f"  Reading level: {p.get('reading_level', '-')}")
    print(f"  Source URL   : {p.get('source_url', '-')}")
    print(f"  Source title : {p.get('source_title', '-')}")
    print(f"  Last used at : {p.get('last_used_at', '-')}")
    print(f"  {'-' * 60}")
    text = p.get("text", "")
    # wrap long text for readability
    wrapped = textwrap.fill(text, width=80, initial_indent="  ", subsequent_indent="  ")
    print(f"  Text:")
    print(wrapped)
    print(f"  {'=' * 60}\n")

    await client.close()


async def cmd_search(
    query: str, collection: str, limit: int, filters_str: str | None,
) -> None:
    """Semantic search across passages."""
    client = await _get_client()
    if not await client.collection_exists(collection):
        print(f"  Collection '{collection}' does not exist.")
        await client.close()
        return

    qdrant_filter = _parse_filters(filters_str)

    # Embed the query using the same model as QdrantManager
    from sentence_transformers import SentenceTransformer
    prefix = settings.EMBEDDING_QUERY_PREFIX
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    vector: list[float] = model.encode(prefix + query, convert_to_numpy=False).tolist()

    hits = await client.query_points(
        collection_name=collection,
        query=vector,
        query_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
    )

    if not hits.points:
        print(f"  No results for '{query}'.")
        await client.close()
        return

    rows = []
    for pt in hits.points:
        p = pt.payload or {}
        rows.append([
            f"{pt.score:.3f}",
            pt.id[:8] + "...",
            p.get("passage_type", "—"),
            p.get("passage_category", "—"),
            str(p.get("word_count", "—")),
            p.get("source_title", "—")[:40],
        ])

    print(f"\n  Search results for: '{query}'  |  {collection}")
    print()
    _print_table(rows, ["Score", "ID", "Type", "Category", "Words", "Source"])
    print()

    await client.close()


async def cmd_delete(passage_id: str, collection: str | None, force: bool) -> None:
    """Delete a passage by ID from one or both collections."""
    client = await _get_client()
    collections_to_check = [collection] if collection else list(COLLECTIONS)

    deleted = 0
    for col in collections_to_check:
        if not await client.collection_exists(col):
            continue
        # Check it exists first
        hits = await client.retrieve(
            collection_name=col,
            ids=[passage_id],
            with_payload=False,
            with_vectors=False,
        )
        if not hits:
            continue

        if not force:
            print(f"  Found in '{col}'. Are you sure? [y/N] ", end="", flush=True)
            answer = sys.stdin.readline().strip().lower()
            if answer != "y":
                print(f"  Skipped '{col}'.")
                continue

        from qdrant_client.models import PointIdsList
        await client.delete(
            collection_name=col,
            points_selector=PointIdsList(points=[passage_id]),
        )
        print(f"  Deleted from '{col}'.")
        deleted += 1

    if deleted == 0:
        print(f"  No passage found with ID '{passage_id}'.")
    await client.close()


async def cmd_stats() -> None:
    """Aggregate stats per collection."""
    client = await _get_client()

    for name in COLLECTIONS:
        if not await client.collection_exists(name):
            print(f"\n  {name}: does not exist\n")
            continue

        count_result = await client.count(name)
        total = count_result.count
        if total == 0:
            print(f"\n  {'=' * 50}")
            print(f"  {name}")
            print(f"  {'=' * 50}")
            print(f"    Total passages: 0\n")
            continue

        # Scroll all payloads (no vectors needed) to compute stats
        # ponytail: scroll in batches of 100; fine for typical library sizes
        types: dict[str, int] = {}
        categories: dict[str, int] = {}
        reading_levels: list[float] = []
        word_counts: list[int] = []
        offset = None

        while True:
            hits, next_offset = await client.scroll(
                collection_name=name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for pt in hits:
                p = pt.payload or {}
                t = p.get("passage_type", "unknown")
                types[t] = types.get(t, 0) + 1
                c = p.get("passage_category", "unknown")
                categories[c] = categories.get(c, 0) + 1
                rl = p.get("reading_level")
                if rl is not None:
                    reading_levels.append(float(rl))
                wc = p.get("word_count")
                if wc is not None:
                    word_counts.append(int(wc))

            if next_offset is None:
                break
            offset = next_offset

        avg_rl = sum(reading_levels) / len(reading_levels) if reading_levels else 0.0
        avg_wc = sum(word_counts) / len(word_counts) if word_counts else 0

        print(f"\n  {'=' * 50}")
        print(f"  {name}")
        print(f"  {'=' * 50}")
        print(f"  Total passages       : {total}")
        print(f"  Average reading level: {avg_rl:.1f}")
        print(f"  Average word count   : {avg_wc:.0f}")
        print(f"  Reading level range  : {min(reading_levels):.1f} – {max(reading_levels):.1f}")
        print()

        # Type breakdown
        print(f"  By type:")
        for t in ("long", "short"):
            print(f"    {t:<20} {types.get(t, 0)}")
        print()

        # Category breakdown (sorted by count desc)
        print(f"  By category:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            bar = "#" * max(1, count * 30 // max(categories.values()))
            print(f"    {cat:<20} {count:<5} {bar}")
        print()

    await client.close()


# ── CLI dispatcher ───────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Qdrant passage CRUD and visualization tool",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # collections
    sub.add_parser("collections", help="List collections and point counts")

    # list
    p_list = sub.add_parser("list", help="List passages in a collection")
    p_list.add_argument("--collection", default=COLLECTION_LONG,
                        help=f"Collection name (default: {COLLECTION_LONG})")
    p_list.add_argument("--limit", type=int, default=20, help="Max passages to show")
    p_list.add_argument("--offset", type=int, default=0, help="Scroll offset")

    # get
    p_get = sub.add_parser("get", help="Get passage details by ID")
    p_get.add_argument("passage_id", help="Passage UUID")
    p_get.add_argument("--collection", default=COLLECTION_LONG,
                       help=f"Collection to search (default: {COLLECTION_LONG})")

    # search
    p_search = sub.add_parser("search", help="Semantic search across passages")
    p_search.add_argument("query", help="Search query text")
    p_search.add_argument("--collection", default=COLLECTION_LONG,
                          help=f"Collection (default: {COLLECTION_LONG})")
    p_search.add_argument("--limit", type=int, default=10, help="Max results")
    p_search.add_argument("--filters", help='JSON filters (PowerShell: --filters \'{"key": "val"}\'; bash: --filters \'{"key":"val"}\')')

    # delete
    p_delete = sub.add_parser("delete", help="Delete passage by ID")
    p_delete.add_argument("passage_id", help="Passage UUID to delete")
    p_delete.add_argument("--collection", help="Restrict to one collection")
    p_delete.add_argument("--force", "-f", action="store_true",
                          help="Skip confirmation prompt")

    # stats
    sub.add_parser("stats", help="Aggregate statistics per collection")

    args = parser.parse_args()

    cmd_map = {
        "collections": lambda: cmd_collections(),
        "list": lambda: cmd_list(args.collection, args.limit, args.offset),
        "get": lambda: cmd_get(args.passage_id, args.collection),
        "search": lambda: cmd_search(args.query, args.collection, args.limit, args.filters),
        "delete": lambda: cmd_delete(args.passage_id, args.collection, args.force),
        "stats": lambda: cmd_stats(),
    }

    asyncio.run(cmd_map[args.command]())


if __name__ == "__main__":
    main()
