from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.db.connection import connect
from app.positions import apply_manual_trade, ensure_positions_tables, list_positions

router = APIRouter(prefix="/api/investments", tags=["investments"])


class TradePayload(BaseModel):
    account_id: int = Field(gt=0)
    ticker: str = Field(min_length=1, max_length=16)
    side: str = Field(...)
    quantity_q4: int = Field(gt=0)
    price_q4: int = Field(gt=0)
    fee_cents: int = Field(default=0, ge=0)
    trade_date: str | None = None

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        return normalized


@router.get("/positions")
def list_investment_positions(request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    ensure_positions_tables()
    return list_positions()


@router.get("/accounts")
def list_investment_accounts(request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, code, name, subtype, is_investment, is_archived
            FROM accounts
            WHERE subtype = 'brokerage' OR is_investment = 1
            ORDER BY name ASC
            """
        ).fetchall()
    return {"accounts": [dict(row) for row in rows]}


@router.post("/positions")
def create_position_trade(payload: TradePayload, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return apply_manual_trade(
        account_id=payload.account_id,
        ticker=payload.ticker,
        side=payload.side,
        quantity_q4=payload.quantity_q4,
        price_q4=payload.price_q4,
        fee_cents=payload.fee_cents,
        trade_date=payload.trade_date,
    )


@router.post("/trades")
def create_trade(payload: TradePayload, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return apply_manual_trade(
        account_id=payload.account_id,
        ticker=payload.ticker,
        side=payload.side,
        quantity_q4=payload.quantity_q4,
        price_q4=payload.price_q4,
        fee_cents=payload.fee_cents,
        trade_date=payload.trade_date,
    )
