"""EST Synthesizer - Blueprint Storage (SQLite)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from backend.app.blueprint.default import DEFAULT_BLUEPRINT, HARDER_BLUEPRINT
from backend.app.schemas import TestBlueprint
from backend.app.storage.db import get_connection

logger = logging.getLogger(__name__)

BLUEPRINT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS blueprints (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    blueprint_json  TEXT NOT NULL,
    is_builtin      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
"""


# ── helpers ────────────────────────────────────────────────

def _row_to_dict(row: Any) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "blueprint_json": json.loads(row["blueprint_json"]),
        "is_builtin": bool(row["is_builtin"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ── CRUD ───────────────────────────────────────────────────

async def list_blueprints() -> list[dict]:
    """Return all blueprints ordered by is_builtin DESC, name ASC."""
    async with get_connection() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM blueprints ORDER BY is_builtin DESC, name ASC"
        )
    return [_row_to_dict(r) for r in rows]


async def get_blueprint(bp_id: str) -> dict | None:
    """Get a single blueprint by id, or None."""
    async with get_connection() as db:
        row = await db.execute_fetchall(
            "SELECT * FROM blueprints WHERE id = ?", (bp_id,)
        )
    return _row_to_dict(row[0]) if row else None


async def create_blueprint(
    name: str,
    blueprint_json: dict,
    description: str = "",
    *,
    bp_id: str | None = None,
    is_builtin: bool = False,
) -> dict:
    """Insert a new blueprint and return it."""
    now = datetime.now(timezone.utc).isoformat()
    if bp_id is None:
        bp_id = name.lower().replace(" ", "_").replace("-", "_")
    async with get_connection() as db:
        await db.execute(
            """
            INSERT INTO blueprints (id, name, description, blueprint_json,
                                    is_builtin, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (bp_id, name, description, json.dumps(blueprint_json),
             int(is_builtin), now, now),
        )
        await db.commit()
    result = await get_blueprint(bp_id)
    assert result is not None
    return result


async def update_blueprint(
    bp_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    blueprint_json: dict | None = None,
) -> dict | None:
    """Update fields of an existing blueprint.  Built-in blueprints are
    immutable (raises ``ValueError``)."""
    existing = await get_blueprint(bp_id)
    if existing is None:
        return None
    if existing["is_builtin"]:
        raise ValueError("Built-in blueprints are read-only")

    now = datetime.now(timezone.utc).isoformat()
    fields: dict[str, Any] = {"updated_at": now}
    if name is not None:
        fields["name"] = name
    if description is not None:
        fields["description"] = description
    if blueprint_json is not None:
        fields["blueprint_json"] = json.dumps(blueprint_json)

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [bp_id]

    async with get_connection() as db:
        await db.execute(
            f"UPDATE blueprints SET {set_clause} WHERE id = ?", values
        )
        await db.commit()

    return await get_blueprint(bp_id)


async def delete_blueprint(bp_id: str) -> bool:
    """Delete a custom blueprint.  Built-in blueprints are protected."""
    existing = await get_blueprint(bp_id)
    if existing is None:
        return False
    if existing["is_builtin"]:
        raise ValueError("Built-in blueprints cannot be deleted")
    async with get_connection() as db:
        await db.execute("DELETE FROM blueprints WHERE id = ?", (bp_id,))
        await db.commit()
    return True


async def duplicate_blueprint(bp_id: str) -> dict | None:
    """Duplicate a blueprint (built-in or custom) as a new editable copy."""
    existing = await get_blueprint(bp_id)
    if existing is None:
        return None
    return await create_blueprint(
        name=f"Copy of {existing['name']}",
        blueprint_json=existing["blueprint_json"],
        description=existing["description"],
    )


# ── seed ───────────────────────────────────────────────────

BUILTIN_BLUEPRINTS: list[TestBlueprint] = [
    DEFAULT_BLUEPRINT,
    HARDER_BLUEPRINT,
]


async def seed_builtin_blueprints() -> None:
    """Insert built-in blueprints if they don't already exist."""
    for bp in BUILTIN_BLUEPRINTS:
        existing = await get_blueprint(bp.id)
        if existing is not None:
            continue
        await create_blueprint(
            name=bp.name,
            blueprint_json=bp.model_dump(mode="json"),
            description=bp.name.replace("_", " ").title(),
            bp_id=bp.id,
            is_builtin=True,
        )
        logger.info("Seeded built-in blueprint: %s", bp.id)
