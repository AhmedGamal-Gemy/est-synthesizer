"""EST Synthesizer - Blueprint API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.storage.blueprints import (
    create_blueprint,
    delete_blueprint,
    duplicate_blueprint,
    get_blueprint,
    list_blueprints,
    update_blueprint,
)
from backend.app.schemas import TestBlueprint
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/blueprints", tags=["blueprints"])


# ── request / response models ──────────────────────────────

class BlueprintOut(BaseModel):
    id: str
    name: str
    description: str
    blueprint_json: dict[str, Any]
    is_builtin: bool
    created_at: str
    updated_at: str


class CreateBlueprintIn(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    blueprint_json: dict[str, Any]


class UpdateBlueprintIn(BaseModel):
    name: str | None = None
    description: str | None = None
    blueprint_json: dict[str, Any] | None = None


# ── endpoints ──────────────────────────────────────────────


@router.get("", response_model=list[BlueprintOut])
async def list_all():
    return await list_blueprints()


@router.get("/{bp_id}", response_model=BlueprintOut)
async def get_one(bp_id: str):
    bp = await get_blueprint(bp_id)
    if bp is None:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return bp


@router.post("", response_model=BlueprintOut, status_code=201)
async def create(body: CreateBlueprintIn):
    try:
        TestBlueprint(**body.blueprint_json)  # validate
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    try:
        return await create_blueprint(
            name=body.name,
            blueprint_json=body.blueprint_json,
            description=body.description,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.put("/{bp_id}", response_model=BlueprintOut)
async def update(bp_id: str, body: UpdateBlueprintIn):
    if body.blueprint_json is not None:
        try:
            TestBlueprint(**body.blueprint_json)  # validate
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    try:
        result = await update_blueprint(
            bp_id,
            name=body.name,
            description=body.description,
            blueprint_json=body.blueprint_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return result


@router.delete("/{bp_id}", status_code=204)
async def delete(bp_id: str):
    try:
        deleted = await delete_blueprint(bp_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="Blueprint not found")


@router.post("/{bp_id}/duplicate", response_model=BlueprintOut, status_code=201)
async def duplicate(bp_id: str):
    result = await duplicate_blueprint(bp_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return result
