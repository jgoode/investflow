from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.db.connection import connect
from app.positions import apply_manual_trade, ensure_positions_tables, list_positions
from app.providers import (
    get_latest_quote,
    set_manual_quote,
)

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


class ManualQuotePayload(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    price_q4: int = Field(gt=0)
    asof: str | None = None

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        return value.strip().upper()


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


@router.get("/quote")
@router.get("/quotes")
@router.get("/quotes/{ticker}")
def fetch_quote(
    request: Request,
    ticker: str | None = None,
    tickers: str | None = None,
) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    selection = ticker or tickers
    if selection is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="ticker is required")
    symbols = [item.strip().upper() for item in selection.split(",") if item.strip()]
    if not symbols:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="ticker is required")
    if len(symbols) == 1:
        return get_latest_quote(symbols[0])
    return {"quotes": [get_latest_quote(symbol) for symbol in symbols]}


@router.post("/quote/manual")
@router.post("/quotes/manual")
def create_manual_quote(payload: ManualQuotePayload, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return set_manual_quote(ticker=payload.ticker, price_q4=payload.price_q4, asof=payload.asof)
