from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.accounts import (
    _serialize_account,
    account_tree,
    create_account,
    ensure_seeded_coa,
    update_account_details,
)
from app.db.connection import connect

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountPayload(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    type: str = Field(...)
    subtype: str = Field(default="other")
    parent_id: int | None = None
    institution: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    is_investment: bool = False
    account_number: str | None = Field(default=None, max_length=64)
    routing_transit: str | None = Field(default=None, max_length=64)
    transfer_numbers: str | None = Field(default=None, max_length=256)
    notes: str | None = Field(default=None, max_length=512)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"asset", "liability", "income", "expense", "equity"}
        if normalized not in allowed:
            raise ValueError("invalid account type")
        return normalized

    @field_validator("subtype")
    @classmethod
    def validate_subtype(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"group", "bank", "cash", "brokerage", "credit_card", "fund", "other"}
        if normalized not in allowed:
            raise ValueError("invalid account subtype")
        return normalized

    @model_validator(mode="after")
    def validate_account(self) -> AccountPayload:
        if self.parent_id is not None and self.parent_id <= 0:
            raise ValueError("parent_id must be positive")
        return self


class AccountEditPayload(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    type: str | None = Field(default=None)
    subtype: str | None = Field(default=None)
    parent_id: int | None = None
    institution: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    is_archived: bool | None = None
    is_investment: bool | None = None
    account_number: str | None = Field(default=None, max_length=64)
    routing_transit: str | None = Field(default=None, max_length=64)
    transfer_numbers: str | None = Field(default=None, max_length=256)
    notes: str | None = Field(default=None, max_length=512)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        allowed = {"asset", "liability", "income", "expense", "equity"}
        if normalized not in allowed:
            raise ValueError("invalid account type")
        return normalized

    @field_validator("subtype")
    @classmethod
    def validate_subtype(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        allowed = {"group", "bank", "cash", "brokerage", "credit_card", "fund", "other"}
        if normalized not in allowed:
            raise ValueError("invalid account subtype")
        return normalized


@router.get("/tree")
def list_accounts_tree(request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    ensure_seeded_coa()
    return account_tree()


@router.get("")
def list_accounts(request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    ensure_seeded_coa()

    with connect() as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY name ASC").fetchall()
    return {"accounts": [_serialize_account(row) for row in rows]}


@router.post("")
def create_account_endpoint(payload: AccountPayload, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    ensure_seeded_coa()
    created = create_account(payload.model_dump())
    return {"account": created}


@router.patch("/{account_id}")
def update_account_endpoint(
    account_id: int,
    payload: AccountEditPayload,
    request: Request,
) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    ensure_seeded_coa()
    data = payload.model_dump(exclude_unset=True)
    updated = update_account_details(account_id, payload=data)
    return {"account": updated}
