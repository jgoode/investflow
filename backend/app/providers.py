from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.db.connection import connect

DEFAULT_PROVIDER = "yahoo"
QUOTE_FRESHNESS_SECONDS = 15 * 60


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper()


def _asof_to_utc(value: str | None, *, default_now: datetime | None = None) -> str:
    if value is None:
        anchor = default_now or _utc_now()
        return anchor.isoformat().replace("+00:00", "Z")
    raw = str(value).strip()
    if not raw:
        anchor = default_now or _utc_now()
        return anchor.isoformat().replace("+00:00", "Z")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    normalized = datetime.fromisoformat(raw)
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_settings_table() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                value_type TEXT NOT NULL DEFAULT 'str',
                scope TEXT NOT NULL DEFAULT 'global',
                updated_at INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()


def read_setting(key: str, default: Any = None) -> Any:
    ensure_settings_table()
    with connect() as conn:
        row = conn.execute(
            "SELECT value, value_type FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
    if row is None:
        return default
    value = row["value"]
    value_type = row["value_type"] or "str"
    if value is None:
        return default
    if value_type == "json":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def write_setting(key: str, value: Any, *, value_type: str = "str") -> Any:
    ensure_settings_table()
    payload = value
    if value_type == "json":
        payload = json.dumps(value)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value, value_type, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                value_type = excluded.value_type,
                updated_at = excluded.updated_at
            """,
            (key, payload, value_type, int(time.time())),
        )
        conn.commit()
    return value


def get_selected_provider() -> str:
    selected = str(read_setting("provider.selected", DEFAULT_PROVIDER) or DEFAULT_PROVIDER)
    return selected.strip().lower() or DEFAULT_PROVIDER


def set_selected_provider(name: str) -> str:
    provider = str(name or DEFAULT_PROVIDER).strip().lower()
    if provider not in {"yahoo", "manual"}:
        provider = DEFAULT_PROVIDER
    write_setting("provider.selected", provider, value_type="str")
    return provider


def ensure_market_tables() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_cache (
                id INTEGER PRIMARY KEY,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                close_q4 INTEGER NOT NULL,
                volume INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'manual',
                fetched_at INTEGER NOT NULL,
                UNIQUE(ticker, date)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS latest_quotes (
                ticker TEXT PRIMARY KEY,
                price_q4 INTEGER NOT NULL,
                asof TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                fetched_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def _quote_pack(
    *,
    ticker: str,
    price_q4: int,
    asof: str,
    source: str,
    fetched_at: int,
    now_ts: int,
) -> dict[str, Any]:
    asof_ts = int(
        datetime.fromisoformat(str(asof).replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    )
    age_seconds = max(now_ts - asof_ts, now_ts - int(fetched_at))
    is_stale = age_seconds > QUOTE_FRESHNESS_SECONDS
    badge = f"stale, last price @ {asof}" if is_stale else f"fresh, last price @ {asof}"
    payload = {
        "ticker": ticker,
        "price_q4": int(price_q4),
        "asof": asof,
        "source": source,
        "fetched_at": int(fetched_at),
        "stale": is_stale,
        "status": "stale" if is_stale else "live",
        "badge": badge,
        "provider": source,
    }
    if payload["source"] == "manual":
        payload["provider"] = "manual"
    return payload


def get_latest_quote(ticker: str, *, now_utc: datetime | None = None) -> dict[str, Any]:
    normalized = _normalize_ticker(ticker)
    ensure_market_tables()
    reference_now = now_utc or _utc_now()
    effective_now_ts = max(int(time.time()), int(reference_now.timestamp()))
    with connect() as conn:
        row = conn.execute(
            "SELECT ticker, price_q4, asof, source, fetched_at FROM latest_quotes WHERE ticker = ?",
            (normalized,),
        ).fetchone()
    if row is None:
        return {
            "ticker": normalized,
            "price_q4": 0,
            "asof": "",
            "source": "manual",
            "fetched_at": 0,
            "stale": True,
            "status": "unavailable",
            "badge": "stale, no price available",
            "provider": get_selected_provider(),
        }
    return _quote_pack(
        ticker=str(row["ticker"]),
        price_q4=int(row["price_q4"]),
        asof=str(row["asof"]),
        source=str(row["source"]),
        fetched_at=int(row["fetched_at"]),
        now_ts=effective_now_ts,
    )


def set_manual_quote(
    ticker: str,
    price_q4: int,
    asof: str | None = None,
    *,
    _ignored: Any = None,
) -> dict[str, Any]:
    normalized = _normalize_ticker(ticker)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="ticker is required")
    if int(price_q4) <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="price_q4 must be a positive integer",
        )
    stamp = int(time.time())
    quote_at = _asof_to_utc(asof, default_now=datetime.fromtimestamp(stamp, tz=timezone.utc))
    ensure_market_tables()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO latest_quotes (ticker, price_q4, asof, source, fetched_at)
            VALUES (?, ?, ?, 'manual', ?)
            ON CONFLICT(ticker) DO UPDATE SET
                price_q4 = excluded.price_q4,
                asof = excluded.asof,
                source = excluded.source,
                fetched_at = excluded.fetched_at
            """,
            (normalized, int(price_q4), quote_at, stamp),
        )
        conn.commit()
    return get_latest_quote(normalized, now_utc=datetime.fromtimestamp(stamp, tz=timezone.utc))


class MarketDataProvider(ABC):
    provider_name = "provider"

    @abstractmethod
    def get_quote(
        self,
        ticker: str,
        *,
        client: httpx.Client | httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_history(
        self,
        ticker: str,
        *,
        start: str | None = None,
        end: str | None = None,
        client: httpx.Client | httpx.AsyncClient | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class YahooFinanceAdapter(MarketDataProvider):
    provider_name = "yahoo"

    def get_quote(
        self,
        ticker: str,
        *,
        client: httpx.Client | httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        symbol = _normalize_ticker(ticker)
        local_client = client or httpx.Client(timeout=10.0)
        try:
            response = local_client.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo",
                headers={"User-Agent": "Mozilla/5.0 (InvestFlow market-data adapter)"},
            )
            response.raise_for_status()
            payload = response.json()
            chart = (payload or {}).get("chart", {}).get("result") or []
            if not chart:
                raise ValueError("empty Yahoo chart payload")
            meta = chart[0].get("meta") or {}
            price_value = meta.get("regularMarketPrice")
            if price_value is None:
                price_value = meta.get("previousClose")
            if price_value is None:
                raise ValueError("Yahoo quote missing regularMarketPrice")
            asof_epoch = meta.get("regularMarketTime")
            asof_ts = int(asof_epoch) if asof_epoch is not None else int(time.time())
            asof = datetime.fromtimestamp(asof_ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            price_q4 = int(round(float(price_value) * 10_000))
            fetched_at = int(time.time())
            return _quote_pack(
                ticker=symbol,
                price_q4=price_q4,
                asof=asof,
                source="yahoo",
                fetched_at=fetched_at,
                now_ts=int(time.time()),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"provider unavailable for {symbol}: {exc}",
            ) from exc
        finally:
            if client is None and local_client is not None:
                local_client.close()

    def get_history(
        self,
        ticker: str,
        *,
        start: str | None = None,
        end: str | None = None,
        client: httpx.Client | httpx.AsyncClient | None = None,
    ) -> list[dict[str, Any]]:
        symbol = _normalize_ticker(ticker)
        end_value = end or datetime.now(timezone.utc).date().isoformat()
        return [{"ticker": symbol, "date": end_value, "close_q4": 0, "volume": 0, "source": "yahoo"}]


class ManualAdapter(MarketDataProvider):
    provider_name = "manual"

    def get_quote(
        self,
        ticker: str,
        *,
        client: httpx.Client | httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        symbol = _normalize_ticker(ticker)
        quote = get_latest_quote(symbol)
        if quote["price_q4"] <= 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"manual quote not found for {symbol}")
        return quote

    def get_history(
        self,
        ticker: str,
        *,
        start: str | None = None,
        end: str | None = None,
        client: httpx.Client | httpx.AsyncClient | None = None,
    ) -> list[dict[str, Any]]:
        return []


PROVIDERS: dict[str, type[MarketDataProvider]] = {"yahoo": YahooFinanceAdapter, "manual": ManualAdapter}


def fetch_quote_via_provider(ticker: str, *, provider_name: str | None = None) -> dict[str, Any]:
    provider_key = str(provider_name or get_selected_provider()).strip().lower() or DEFAULT_PROVIDER
    adapter_cls = PROVIDERS.get(provider_key, YahooFinanceAdapter)
    try:
        quote = adapter_cls().get_quote(ticker)
    except Exception:
        fallback = get_latest_quote(ticker)
        return fallback
    if quote.get("source") == "yahoo":
        stamp = int(time.time())
        ensure_market_tables()
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO latest_quotes (ticker, price_q4, asof, source, fetched_at)
                VALUES (?, ?, ?, 'yahoo', ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    price_q4 = excluded.price_q4,
                    asof = excluded.asof,
                    source = excluded.source,
                    fetched_at = excluded.fetched_at
                """,
                (_normalize_ticker(ticker), int(quote["price_q4"]), str(quote["asof"]), stamp),
            )
            conn.commit()
    return get_latest_quote(ticker, now_utc=datetime.fromtimestamp(int(time.time()), tz=timezone.utc))


def resolve_quote(ticker: str, *, now_utc: datetime | None = None) -> dict[str, Any]:
    normalized = _normalize_ticker(ticker)
    quote = get_latest_quote(normalized, now_utc=now_utc)
    if quote["price_q4"] > 0 and (quote["source"] == "manual" or not quote["stale"]):
        return quote
    selected = get_selected_provider()
    if selected == "manual":
        return quote
    try:
        return fetch_quote_via_provider(normalized)
    except Exception:
        return quote

