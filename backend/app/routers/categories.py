from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.categories import (
    assign_category_to_line,
    create_category,
    delete_category,
    ensure_seeded_categories,
    list_categories,
    update_category,
)

router = APIRouter(prefix="/api/categories", tags=["categories"])


class CategoryPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    flow: str
    color: str = Field(default="#64748b", min_length=1, max_length=16)
    default_account_id: int | None = None

    @field_validator("flow")
    @classmethod
    def validate_flow(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"income", "expense"}:
            raise ValueError("invalid category flow")
        return normalized


class CategoryEditPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    flow: str | None = None
    color: str | None = Field(default=None, min_length=1, max_length=16)
    default_account_id: int | None = None

    @field_validator("flow")
    @classmethod
    def validate_flow(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"income", "expense"}:
            raise ValueError("invalid category flow")
        return normalized


class CategoryDeletePayload(BaseModel):
    confirm: bool


class CategoryAssignPayload(BaseModel):
    category_id: int | None = None


def _ensure_authenticated(request: Request) -> None:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


@router.get("")
def categories_list(request: Request) -> dict[str, Any]:
    _ensure_authenticated(request)
    ensure_seeded_categories()
    return {"categories": list_categories()}


@router.post("")
def create_category_endpoint(payload: CategoryPayload, request: Request) -> dict[str, Any]:
    _ensure_authenticated(request)
    ensure_seeded_categories()
    category = create_category(payload.model_dump())
    return {"category": category}


@router.patch("/{category_id}")
def update_category_endpoint(
    category_id: int, payload: CategoryEditPayload, request: Request
) -> dict[str, Any]:
    _ensure_authenticated(request)
    ensure_seeded_categories()
    category = update_category(category_id, payload.model_dump(exclude_unset=True))
    return {"category": category}


@router.delete("/{category_id}")
def delete_category_endpoint(
    category_id: int, payload: CategoryDeletePayload, request: Request
) -> dict[str, str]:
    _ensure_authenticated(request)
    ensure_seeded_categories()
    delete_category(category_id, confirm=payload.confirm)
    return {"status": "ok"}


@router.patch("/lines/{line_id}")
def assign_category_endpoint(
    line_id: int, payload: CategoryAssignPayload, request: Request
) -> dict[str, Any]:
    _ensure_authenticated(request)
    ensure_seeded_categories()
    line = assign_category_to_line(line_id, payload.category_id)
    return {"line": line}
