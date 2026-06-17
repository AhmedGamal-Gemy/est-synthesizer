"""Integration tests for blueprint API routes via TestClient."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.blueprint.default import DEFAULT_BLUEPRINT
from backend.app.schemas import TestBlueprint


# ── Valid blueprint JSON for test payloads ──────────────────

_BLUEPRINT_JSON = DEFAULT_BLUEPRINT.model_dump(mode="json")


# ── Test client fixture ─────────────────────────────────────


@pytest.fixture
async def client():
    """Async HTTP test client with seeded DB, Qdrant mocked, strict validation patched."""
    import aiosqlite
    import backend.app.storage.db as db_mod
    from backend.app.storage.db import SCHEMA_SQL
    from backend.app.storage.blueprints import seed_builtin_blueprints

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()

    original_conn = db_mod._conn
    original_path = db_mod.DB_PATH
    db_mod._conn = conn
    db_mod.DB_PATH = ":memory:"
    try:
        await seed_builtin_blueprints()

        # Mock lifespan to skip init_db (already done) and Qdrant init
        import backend.app.main as main_mod
        from contextlib import asynccontextmanager

        original_lifespan = main_mod.app.router.lifespan_context

        @asynccontextmanager
        async def mock_lifespan(app):
            yield

        main_mod.app.router.lifespan_context = mock_lifespan

        # Patch TestBlueprint in route module to use model_validate(strict=False)
        # because the route calls TestBlueprint(**body.blueprint_json) which fails
        # with strict=True for JSON dicts containing (str, Enum) auto values.
        import backend.app.routes.blueprints as route_mod

        original_route_tb = route_mod.TestBlueprint

        class _ValidatingTestBlueprint:
            """Replaces TestBlueprint(**kwargs) calls in the route with
            model_validate(kwargs, strict=False) so JSON dicts pass validation."""

            def __init__(self, **kwargs):
                TestBlueprint.model_validate(kwargs, strict=False)

        route_mod.TestBlueprint = _ValidatingTestBlueprint

        transport = ASGITransport(app=main_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    finally:
        route_mod.TestBlueprint = original_route_tb
        main_mod.app.router.lifespan_context = original_lifespan
        db_mod._conn = original_conn
        db_mod.DB_PATH = original_path
        await conn.close()


# ── GET tests ───────────────────────────────────────────────


class TestGetBlueprints:
    async def test_list_returns_two_builtin_blueprints(self, client):
        response = await client.get("/api/blueprints")
        assert response.status_code == 200
        data = response.json()
        builtin_count = sum(1 for bp in data if bp["is_builtin"])
        assert builtin_count == 2

    async def test_get_existing_blueprint(self, client):
        response = await client.get(f"/api/blueprints/{DEFAULT_BLUEPRINT.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == DEFAULT_BLUEPRINT.id
        assert data["is_builtin"] is True

    async def test_get_nonexistent_blueprint_returns_404(self, client):
        response = await client.get("/api/blueprints/nonexistent-id")
        assert response.status_code == 404


# ── POST tests ──────────────────────────────────────────────


class TestCreateBlueprint:
    async def test_create_custom_blueprint_returns_201(self, client):
        response = await client.post(
            "/api/blueprints",
            json={
                "name": "My Test Blueprint",
                "description": "Created via test",
                "blueprint_json": _BLUEPRINT_JSON,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Test Blueprint"
        assert data["is_builtin"] is False

    async def test_create_with_invalid_blueprint_json_returns_422(self, client):
        response = await client.post(
            "/api/blueprints",
            json={
                "name": "Bad Blueprint",
                "blueprint_json": {"invalid": "data"},  # not a valid TestBlueprint
            },
        )
        assert response.status_code == 422


# ── PUT tests ───────────────────────────────────────────────


class TestUpdateBlueprint:
    async def test_update_custom_blueprint_name(self, client):
        # Create a custom blueprint first
        create_resp = await client.post(
            "/api/blueprints",
            json={
                "name": "Original",
                "blueprint_json": _BLUEPRINT_JSON,
            },
        )
        assert create_resp.status_code == 201
        bp_id = create_resp.json()["id"]

        # Update its name
        update_resp = await client.put(
            f"/api/blueprints/{bp_id}",
            json={"name": "Updated Name"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Updated Name"

    async def test_update_builtin_blueprint_returns_403(self, client):
        response = await client.put(
            f"/api/blueprints/{DEFAULT_BLUEPRINT.id}",
            json={"name": "Hacked"},
        )
        assert response.status_code == 403


# ── DELETE tests ────────────────────────────────────────────


class TestDeleteBlueprint:
    async def test_delete_custom_blueprint_returns_204(self, client):
        # Create a custom blueprint
        create_resp = await client.post(
            "/api/blueprints",
            json={
                "name": "Delete Me",
                "blueprint_json": _BLUEPRINT_JSON,
            },
        )
        assert create_resp.status_code == 201
        bp_id = create_resp.json()["id"]

        # Delete it
        delete_resp = await client.delete(f"/api/blueprints/{bp_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get(f"/api/blueprints/{bp_id}")
        assert get_resp.status_code == 404

    async def test_delete_builtin_blueprint_returns_403(self, client):
        response = await client.delete(f"/api/blueprints/{DEFAULT_BLUEPRINT.id}")
        assert response.status_code == 403


# ── Duplicate tests ─────────────────────────────────────────


class TestDuplicateBlueprint:
    async def test_duplicate_blueprint_returns_201(self, client):
        response = await client.post(
            f"/api/blueprints/{DEFAULT_BLUEPRINT.id}/duplicate"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == f"Copy of {DEFAULT_BLUEPRINT.name}"
        assert data["is_builtin"] is False

    async def test_duplicate_nonexistent_returns_404(self, client):
        response = await client.post(
            "/api/blueprints/nonexistent-id/duplicate"
        )
        assert response.status_code == 404
