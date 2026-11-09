from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.db.connection import connect
from app.positions import apply_manual_trade, ensure_positions_tables, list_positions
from app.providers import (
    fetch_news_via_provider,
    fetch_profile_via_provider,
    get_latest_quote,
    set_manual_quote,
)
from app.ta import compute_indicator_snapshot

router = APIRouter(prefix="/api/investments", tags=["investments"])


def _detail_market_value_cents(quantity_q4: int, price_q4: int) -> int:
    if quantity_q4 <= 0 or price_q4 <= 0:
        return 0
    return (int(quantity_q4) * int(price_q4)) // 1_000_000


def _fetch_position_row(
    position_id: int | None = None, ticker: str | None = None
) -> dict[str, Any] | None:
    with connect() as conn:
        if position_id is not None:
            row = conn.execute(
                """
                SELECT p.*, a.name AS account_name
                FROM positions p
                JOIN accounts a ON a.id = p.account_id
                WHERE p.id = ?
                """,
                (position_id,),
            ).fetchone()
        elif ticker is not None:
            row = conn.execute(
                """
                SELECT p.*, a.name AS account_name
                FROM positions p
                JOIN accounts a ON a.id = p.account_id
                WHERE p.ticker = ? AND p.status = 'open'
                ORDER BY p.updated_at DESC, p.id DESC
                LIMIT 1
                """,
                (str(ticker).strip().upper(),),
            ).fetchone()
        else:
            return None
    return dict(row) if row is not None else None


def _build_position_detail(position_row: dict[str, Any]) -> dict[str, Any]:
    ticker = str(position_row["ticker"]).upper()
    quote = get_latest_quote(ticker)
    price_q4 = int(quote.get("price_q4") or 0)
    quantity_q4 = int(position_row.get("quantity_q4") or 0)
    avg_cost_q4 = int(position_row.get("avg_cost_q4") or 0)
    market_value_cents = _detail_market_value_cents(quantity_q4, price_q4)
    cost_basis_cents = _detail_market_value_cents(quantity_q4, avg_cost_q4)
    unrealized = market_value_cents - cost_basis_cents
    profile = fetch_profile_via_provider(ticker)
    history = []
    try:
        from app.providers import YahooFinanceAdapter

        history = YahooFinanceAdapter().get_history(ticker)
    except Exception:
        history = []
    close_points = [
        float((item.get("close_q4") or 0) / 10_000.0) for item in history if item.get("close_q4")
    ]
    ta = compute_indicator_snapshot(close_points)
    news = fetch_news_via_provider(ticker)
    return {
        "id": int(position_row["id"]),
        "ticker": ticker,
        "account_id": int(position_row["account_id"]),
        "account_name": position_row.get("account_name"),
        "ticker_summary": {
            "position_id": int(position_row["id"]),
            "ticker": ticker,
            "company_name": profile.get("name") or ticker,
            "sector": profile.get("sector"),
            "exchange": profile.get("exchange") or "N/A",
            "quantity_q4": quantity_q4,
            "avg_cost_q4": avg_cost_q4,
            "market_price_q4": price_q4,
            "market_value_cents": market_value_cents,
            "unrealized_gain_loss_cents": unrealized,
            "stale": bool(quote.get("stale")),
            "status": str(quote.get("status") or "live"),
            "badge": str(quote.get("badge") or "fresh, last price available"),
            "source": str(quote.get("source") or "manual"),
        },
        "valuation_breakdown": {
            "market_value_cents": market_value_cents,
            "cost_basis_cents": cost_basis_cents,
            "unrealized_gain_loss_cents": unrealized,
            "avg_cost_q4": avg_cost_q4,
            "last_price_q4": price_q4,
            "position_quantity_q4": quantity_q4,
        },
        "historical_context": {
            "price_points": [
                {
                    "date": item.get("date"),
                    "close_q4": int(item.get("close_q4") or 0),
                    "volume": int(item.get("volume") or 0),
                }
                for item in history
            ],
            "technical_analysis": ta,
        },
        "news": news,
        "technical_analysis": ta,
    }


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


@router.get("/positions/{identifier}/detail")
def get_position_detail(request: Request, identifier: str) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    ensure_positions_tables()
    try:
        position_id = int(identifier)
        row = _fetch_position_row(position_id=position_id)
    except ValueError:
        row = _fetch_position_row(ticker=identifier)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="position not found")
    return _build_position_detail(row)


@router.get("/positions/{position_id}")
def get_position_by_id(request: Request, position_id: int) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    row = _fetch_position_row(position_id=position_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="position not found")
    return _build_position_detail(row)


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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="ticker is required"
        )
    symbols = [item.strip().upper() for item in selection.split(",") if item.strip()]
    if not symbols:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="ticker is required"
        )
    if len(symbols) == 1:
        return get_latest_quote(symbols[0])
    return {"quotes": [get_latest_quote(symbol) for symbol in symbols]}


@router.post("/quote/manual")
@router.post("/quotes/manual")
def create_manual_quote(payload: ManualQuotePayload, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return set_manual_quote(ticker=payload.ticker, price_q4=payload.price_q4, asof=payload.asof)
