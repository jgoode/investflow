from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.transactions import (
    create_transaction,
    get_transaction,
    list_transactions,
    update_transaction,
    void_transaction,
)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class TransactionLinePayload(BaseModel):
    account_id: int = Field(gt=0)
    direction: str
    amount_cents: int = Field(gt=0)
    memo: str | None = None
    category_id: int | None = Field(default=None, gt=0)

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"debit", "credit"}:
            raise ValueError("direction must be debit or credit")
        return normalized


class TransactionPayload(BaseModel):
    date: str
    description: str = Field(min_length=1, max_length=256)
    reference: str | None = Field(default=None, max_length=128)
    lines: list[TransactionLinePayload] = Field(default_factory=list)
    mode: str | None = None
    account_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    amount_cents: int | None = Field(default=None, gt=0)
    target_account_id: int | None = Field(default=None, gt=0)
    account_target_id: int | None = Field(default=None, gt=0)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"income", "expense", "transfer"}:
            raise ValueError("mode must be income, expense, or transfer")
        return normalized

    @model_validator(mode="after")
    def ensure_lines_or_quick_post(self) -> TransactionPayload:
        if not self.lines and self.mode is None:
            raise ValueError("lines or a quick-post mode is required")
        return self


class TransactionUpdatePayload(BaseModel):
    date: str | None = None
    description: str | None = Field(default=None, min_length=1, max_length=256)
    reference: str | None = Field(default=None, max_length=128)
    status: str | None = None
    lines: list[TransactionLinePayload] | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"posted", "void"}:
            raise ValueError("status must be posted or void")
        return normalized


@router.get("")
def list_transactions_endpoint(request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    payload = list_transactions(
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        account_id=int(request.query_params["account_id"])
        if request.query_params.get("account_id")
        else None,
        account_type=request.query_params.get("account_type"),
        category_id=int(request.query_params["category_id"])
        if request.query_params.get("category_id")
        else None,
        amount_min_cents=int(request.query_params["amount_min_cents"])
        if request.query_params.get("amount_min_cents")
        else None,
        amount_max_cents=int(request.query_params["amount_max_cents"])
        if request.query_params.get("amount_max_cents")
        else None,
        q=request.query_params.get("q"),
        page=int(request.query_params.get("page", "1")),
        page_size=int(request.query_params.get("page_size", "20")),
        include_void=request.query_params.get("include_void", "false").lower()
        in {"1", "true", "yes"},
    )
    return payload


@router.get("/{transaction_id}")
def get_transaction_endpoint(transaction_id: int, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return {"transaction": get_transaction(transaction_id)}


@router.post("")
def create_transaction_endpoint(payload: TransactionPayload, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    created = create_transaction(
        payload.model_dump(exclude_unset=True),
        created_by=int(request.state.current_user["id"]),
    )
    return {"transaction": created}


@router.patch("/{transaction_id}")
def update_transaction_endpoint(
    transaction_id: int,
    payload: TransactionUpdatePayload,
    request: Request,
) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    updated = update_transaction(
        transaction_id,
        payload.model_dump(exclude_unset=True),
        created_by=int(request.state.current_user["id"]),
    )
    return {"transaction": updated}


@router.post("/{transaction_id}/void")
def void_transaction_endpoint(transaction_id: int, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    voided = void_transaction(transaction_id, user_id=int(request.state.current_user["id"]))
    return {"transaction": voided}


@router.delete("/{transaction_id}")
def delete_transaction_endpoint(transaction_id: int, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    voided = void_transaction(transaction_id, user_id=int(request.state.current_user["id"]))
    return {"transaction": voided}
