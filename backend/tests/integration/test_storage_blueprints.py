"""Integration tests for backend.app.storage.blueprints — Blueprint CRUD."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.app.blueprint.default import DEFAULT_BLUEPRINT, HARDER_BLUEPRINT


# ── seeded_db fixture ────────────────────────────────────────


@pytest.fixture
async def seeded_db():
    """In-memory DB with schema and built-in blueprints seeded."""
    import aiosqlite
    import backend.app.storage.db as db_mod
    from backend.app.storage.blueprints import seed_builtin_blueprints

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(db_mod.SCHEMA_SQL)
    await conn.commit()

    original_conn = db_mod._conn
    original_path = db_mod.DB_PATH
    db_mod._conn = conn
    db_mod.DB_PATH = ":memory:"
    try:
        await seed_builtin_blueprints()
        yield conn
    finally:
        db_mod._conn = original_conn
        db_mod.DB_PATH = original_path
        await conn.close()


# ── _row_to_dict (pure function) ─────────────────────────────


class TestRowToDict:
    def test_row_to_dict_converts_row_to_dict_with_parsed_json(self):
        from backend.app.storage.blueprints import _row_to_dict

        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda key: {
            "id": "bp-001",
            "name": "Test Blueprint",
            "description": "A test description",
            "blueprint_json": json.dumps({"id": "bp-001", "name": "Test"}),
            "is_builtin": 1,
            "created_at": "2024-06-15T10:00:00+00:00",
            "updated_at": "2024-06-15T10:00:00+00:00",
        }[key])

        result = _row_to_dict(row)
        assert result["id"] == "bp-001"
        assert result["name"] == "Test Blueprint"
        assert result["description"] == "A test description"
        assert result["blueprint_json"] == {"id": "bp-001", "name": "Test"}
        assert result["is_builtin"] is True  # 1 → True
        assert result["created_at"] == "2024-06-15T10:00:00+00:00"

    def test_row_to_dict_is_builtin_false(self):
        from backend.app.storage.blueprints import _row_to_dict

        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda key: {
            "id": "bp-002",
            "name": "Custom BP",
            "description": "",
            "blueprint_json": "{}",
            "is_builtin": 0,
            "created_at": "2024-06-15T10:00:00+00:00",
            "updated_at": "2024-06-15T10:00:00+00:00",
        }[key])

        result = _row_to_dict(row)
        assert result["is_builtin"] is False  # 0 → False


# ── CRUD tests ───────────────────────────────────────────────


class TestListBlueprints:
    async def test_returns_at_least_two_builtin_blueprints(self, seeded_db):
        from backend.app.storage.blueprints import list_blueprints

        results = await list_blueprints()
        assert len(results) >= 2
        builtin_ids = {DEFAULT_BLUEPRINT.id, HARDER_BLUEPRINT.id}
        found_ids = {r["id"] for r in results if r["is_builtin"]}
        assert builtin_ids == found_ids


class TestGetBlueprint:
    async def test_get_existing_blueprint(self, seeded_db):
        from backend.app.storage.blueprints import get_blueprint

        result = await get_blueprint(DEFAULT_BLUEPRINT.id)
        assert result is not None
        assert result["id"] == DEFAULT_BLUEPRINT.id
        assert result["is_builtin"] is True

    async def test_get_nonexistent_blueprint(self, seeded_db):
        from backend.app.storage.blueprints import get_blueprint

        result = await get_blueprint("nonexistent-id")
        assert result is None


class TestCreateBlueprint:
    async def test_create_custom_blueprint(self, seeded_db):
        from backend.app.storage.blueprints import create_blueprint, list_blueprints

        bp_json = DEFAULT_BLUEPRINT.model_dump(mode="json")
        result = await create_blueprint(
            name="My Custom BP",
            blueprint_json=bp_json,
            description="A custom blueprint",
        )
        assert result is not None
        assert result["name"] == "My Custom BP"
        assert result["is_builtin"] is False

        # Verify it appears in list
        all_bps = await list_blueprints()
        custom_ids = [r["id"] for r in all_bps if not r["is_builtin"]]
        assert result["id"] in custom_ids


class TestUpdateBlueprint:
    async def test_update_custom_blueprint_name(self, seeded_db):
        from backend.app.storage.blueprints import create_blueprint, update_blueprint

        bp_json = DEFAULT_BLUEPRINT.model_dump(mode="json")
        created = await create_blueprint(
            name="Original Name",
            blueprint_json=bp_json,
        )

        updated = await update_blueprint(created["id"], name="Updated Name")
        assert updated is not None
        assert updated["name"] == "Updated Name"

    async def test_update_builtin_raises_value_error(self, seeded_db):
        from backend.app.storage.blueprints import update_blueprint

        with pytest.raises(ValueError, match="Built-in blueprints are read-only"):
            await update_blueprint(DEFAULT_BLUEPRINT.id, name="Hacked Name")

    async def test_update_nonexistent_returns_none(self, seeded_db):
        from backend.app.storage.blueprints import update_blueprint

        result = await update_blueprint("nonexistent-id", name="New Name")
        assert result is None


class TestDeleteBlueprint:
    async def test_delete_custom_blueprint(self, seeded_db):
        from backend.app.storage.blueprints import create_blueprint, delete_blueprint, get_blueprint

        bp_json = DEFAULT_BLUEPRINT.model_dump(mode="json")
        created = await create_blueprint(
            name="Delete Me",
            blueprint_json=bp_json,
        )

        deleted = await delete_blueprint(created["id"])
        assert deleted is True

        # Verify it's gone
        result = await get_blueprint(created["id"])
        assert result is None

    async def test_delete_builtin_raises_value_error(self, seeded_db):
        from backend.app.storage.blueprints import delete_blueprint

        with pytest.raises(ValueError, match="Built-in blueprints cannot be deleted"):
            await delete_blueprint(DEFAULT_BLUEPRINT.id)

    async def test_delete_nonexistent_returns_false(self, seeded_db):
        from backend.app.storage.blueprints import delete_blueprint

        deleted = await delete_blueprint("nonexistent-id")
        assert deleted is False


class TestDuplicateBlueprint:
    async def test_duplicate_builtin_as_editable_copy(self, seeded_db):
        from backend.app.storage.blueprints import duplicate_blueprint

        result = await duplicate_blueprint(DEFAULT_BLUEPRINT.id)
        assert result is not None
        assert result["name"] == f"Copy of {DEFAULT_BLUEPRINT.name}"
        assert result["is_builtin"] is False
        # Blueprint JSON should be same as the original
        assert result["blueprint_json"]["id"] == DEFAULT_BLUEPRINT.id

    async def test_duplicate_nonexistent_returns_none(self, seeded_db):
        from backend.app.storage.blueprints import duplicate_blueprint

        result = await duplicate_blueprint("nonexistent-id")
        assert result is None


class TestSeedIdempotent:
    async def test_seed_called_twice_still_only_two_builtins(self, seeded_db):
        from backend.app.storage.blueprints import seed_builtin_blueprints

        # Call seed again (already seeded by fixture)
        await seed_builtin_blueprints()

        from backend.app.storage.blueprints import list_blueprints
        results = await list_blueprints()
        builtin_count = sum(1 for r in results if r["is_builtin"])
        assert builtin_count == 2
