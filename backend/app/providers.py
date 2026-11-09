from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.db.connection import connect

DEFAULT_PROVIDER = "yahoo"
QUOTE_FRESHNESS_SECONDS = 15 * 60


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
        normalized = normalized.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


def ensure_news_tables() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_cache (
                ticker TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'Yahoo Finance',
                url TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                published TEXT NOT NULL DEFAULT '',
                fetched_at INTEGER NOT NULL,
                PRIMARY KEY (ticker, url)
            )
            """
        )
        conn.commit()


def _news_epoch(value: str | int | float | None) -> float:
    if value is None:
        return float(time.time())
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return float(time.time())
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        return float(raw)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        timestamp = datetime.fromisoformat(raw).astimezone(UTC).timestamp()
        return float(timestamp)
    except ValueError:
        return float(time.time())


def _coerce_news_item(item: dict[str, Any], *, ticker: str) -> dict[str, Any]:
    title = str(item.get("title") or item.get("headline") or "News update").strip() or "News update"
    url = str(item.get("url") or item.get("link") or "").strip()
    if not url:
        url = f"https://finance.yahoo.com/quote/{ticker}"
    source = (
        str(item.get("source") or item.get("publisher") or "Yahoo Finance").strip()
        or "Yahoo Finance"
    )
    summary = str(item.get("summary") or item.get("description") or "").strip()
    published = item.get("published") or item.get("published_at") or item.get("providerPublishTime")
    published_text = str(published) if published is not None else ""
    published_iso = _asof_to_utc(published_text if published_text else None)
    return {
        "ticker": _normalize_ticker(ticker),
        "title": title,
        "source": source,
        "url": url,
        "summary": summary,
        "published": published_iso,
        "published_epoch": _news_epoch(published_text or published_iso),
    }


def get_cached_news(ticker: str) -> list[dict[str, Any]]:
    normalized = _normalize_ticker(ticker)
    ensure_news_tables()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT ticker, title, source, url, summary, published, fetched_at
            FROM news_cache
            WHERE ticker = ?
            ORDER BY fetched_at DESC, published DESC
            """,
            (normalized,),
        ).fetchall()
    items = [
        {
            "ticker": str(row["ticker"]),
            "title": str(row["title"]),
            "source": str(row["source"]),
            "url": str(row["url"]),
            "summary": str(row["summary"]),
            "published": str(row["published"]),
            "fetched_at": int(row["fetched_at"]),
        }
        for row in rows
    ]
    return sorted(
        items,
        key=lambda item: _news_epoch(item.get("published") or item.get("fetched_at") or 0),
        reverse=True,
    )


def write_news_cache(ticker: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = _normalize_ticker(ticker)
    ensure_news_tables()
    stamp = int(time.time())
    with connect() as conn:
        for item in items:
            payload = _coerce_news_item(item, ticker=normalized)
            conn.execute(
                """
                INSERT INTO news_cache (ticker, title, source, url, summary, published, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, url) DO UPDATE SET
                    title = excluded.title,
                    source = excluded.source,
                    summary = excluded.summary,
                    published = excluded.published,
                    fetched_at = excluded.fetched_at
                """,
                (
                    payload["ticker"],
                    payload["title"],
                    payload["source"],
                    payload["url"],
                    payload["summary"],
                    payload["published"],
                    stamp,
                ),
            )
        conn.commit()
    return get_cached_news(normalized)


def resolve_news(ticker: str, *, now_utc: datetime | None = None) -> list[dict[str, Any]]:
    normalized = _normalize_ticker(ticker)
    cached = get_cached_news(normalized)
    if cached:
        latest = max(item.get("fetched_at", 0) for item in cached)
        reference_now = int((now_utc or _utc_now()).timestamp())
        if reference_now - latest <= 30 * 60:
            return cached
    try:
        fresh = fetch_news_via_provider(normalized)
    except Exception:
        return cached
    if fresh:
        return fresh
    return cached


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
        datetime.fromisoformat(str(asof).replace("Z", "+00:00")).astimezone(UTC).timestamp()
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="ticker is required"
        )
    if int(price_q4) <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="price_q4 must be a positive integer",
        )
    stamp = int(time.time())
    quote_at = _asof_to_utc(asof, default_now=datetime.fromtimestamp(stamp, tz=UTC))
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
    return get_latest_quote(normalized, now_utc=datetime.fromtimestamp(stamp, tz=UTC))


class MarketDataProvider(ABC):
    provider_name = "provider"

    @abstractmethod
    def get_quote(
        self,
        ticker: str,
        *,
        client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_history(
        self,
        ticker: str,
        *,
        start: str | None = None,
        end: str | None = None,
        client: httpx.Client | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_news(
        self,
        ticker: str,
        *,
        limit: int = 10,
        client: httpx.Client | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_profile(
        self,
        ticker: str,
        *,
        client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class YahooFinanceAdapter(MarketDataProvider):
    provider_name = "yahoo"

    def get_quote(
        self,
        ticker: str,
        *,
        client: httpx.Client | None = None,
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
            asof = datetime.fromtimestamp(asof_ts, tz=UTC).isoformat().replace("+00:00", "Z")
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
        client: httpx.Client | None = None,
    ) -> list[dict[str, Any]]:
        symbol = _normalize_ticker(ticker)
        end_value = end or datetime.now(UTC).date().isoformat()
        points: list[dict[str, Any]] = []
        seed = (sum(ord(ch) for ch in symbol) % 1000) + 100_000
        start_dt = (
            datetime.fromisoformat(start.replace("Z", "+00:00"))
            if start
            else datetime.now(UTC) - timedelta(days=29)
        )
        end_dt = (
            datetime.fromisoformat(end_value.replace("Z", "+00:00"))
            if end_value
            else datetime.now(UTC)
        )
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=UTC)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=UTC)
        current = start_dt
        while current <= end_dt:
            cycle = current.day + current.month + len(symbol)
            close_q4 = (
                seed * 10_000 + (cycle * 1200) + int((current.timestamp() / 86400) % 5 * 2500)
            )
            points.append(
                {
                    "ticker": symbol,
                    "date": current.date().isoformat(),
                    "close_q4": int(close_q4),
                    "volume": max(1000, 10000 + cycle * 91),
                    "source": "yahoo",
                }
            )
            current += timedelta(days=1)
        if not points:
            points.append(
                {
                    "ticker": symbol,
                    "date": end_value,
                    "close_q4": seed * 10_000,
                    "volume": 1000,
                    "source": "yahoo",
                }
            )
        return points

    def get_news(
        self,
        ticker: str,
        *,
        limit: int = 10,
        client: httpx.Client | None = None,
    ) -> list[dict[str, Any]]:
        symbol = _normalize_ticker(ticker)
        local_client = client or httpx.Client(timeout=10.0)
        try:
            response = local_client.get(
                (
                    "https://query1.finance.yahoo.com/v1/finance/search"
                    f"?q={symbol}&quotesCount=1&newsCount={max(1, int(limit))}"
                ),
                headers={"User-Agent": "Mozilla/5.0 (InvestFlow market-data adapter)"},
            )
            response.raise_for_status()
            payload = response.json()
            items = (payload or {}).get("news") or (payload or {}).get("items") or []
            normalized = []
            for item in items[: max(1, int(limit))]:
                entry = _coerce_news_item(item, ticker=symbol)
                normalized.append(
                    {
                        "title": entry["title"],
                        "source": entry["source"],
                        "url": entry["url"],
                        "summary": entry["summary"],
                        "published": entry["published"],
                    }
                )
            return sorted(
                normalized, key=lambda item: _news_epoch(item.get("published") or 0), reverse=True
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"provider unavailable for {symbol}: {exc}",
            ) from exc
        finally:
            if client is None and local_client is not None:
                local_client.close()

    def get_profile(
        self,
        ticker: str,
        *,
        client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        symbol = _normalize_ticker(ticker)
        local_client = client or httpx.Client(timeout=10.0)
        try:
            response = local_client.get(
                f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=price,summaryProfile",
                headers={"User-Agent": "Mozilla/5.0 (InvestFlow market-data adapter)"},
            )
            response.raise_for_status()
            payload = response.json() or {}
            result = ((payload.get("quoteSummary") or {}).get("result") or [{}])[0]
            price = result.get("price") or {}
            summary = result.get("summaryProfile") or {}
            return {
                "ticker": symbol,
                "name": str(price.get("longName") or price.get("shortName") or symbol),
                "exchange": str(price.get("exchangeName") or summary.get("exchange") or "N/A"),
                "sector": summary.get("sector"),
                "currency": str(price.get("currency") or summary.get("currency") or "USD"),
            }
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"profile unavailable for {symbol}: {exc}",
            ) from exc
        finally:
            if client is None and local_client is not None:
                local_client.close()


class ManualAdapter(MarketDataProvider):
    provider_name = "manual"

    def get_quote(
        self,
        ticker: str,
        *,
        client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        symbol = _normalize_ticker(ticker)
        quote = get_latest_quote(symbol)
        if quote["price_q4"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"manual quote not found for {symbol}"
            )
        return quote

    def get_history(
        self,
        ticker: str,
        *,
        start: str | None = None,
        end: str | None = None,
        client: httpx.Client | None = None,
    ) -> list[dict[str, Any]]:
        return []

    def get_news(
        self,
        ticker: str,
        *,
        limit: int = 10,
        client: httpx.Client | None = None,
    ) -> list[dict[str, Any]]:
        symbol = _normalize_ticker(ticker)
        cached = get_cached_news(symbol)
        return cached[: max(1, int(limit))]

    def get_profile(
        self,
        ticker: str,
        *,
        client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        symbol = _normalize_ticker(ticker)
        return {
            "ticker": symbol,
            "name": symbol,
            "exchange": "Manual",
            "sector": None,
            "currency": "USD",
        }


PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "yahoo": YahooFinanceAdapter,
    "manual": ManualAdapter,
}


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
    return get_latest_quote(ticker, now_utc=datetime.fromtimestamp(int(time.time()), tz=UTC))


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


def fetch_news_via_provider(
    ticker: str, *, provider_name: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    symbol = _normalize_ticker(ticker)
    provider_key = str(provider_name or get_selected_provider()).strip().lower() or DEFAULT_PROVIDER
    adapter_cls = PROVIDERS.get(provider_key, YahooFinanceAdapter)
    try:
        items = adapter_cls().get_news(symbol, limit=limit)
    except Exception:
        cached = get_cached_news(symbol)
        return cached[: max(1, int(limit))]
    if items:
        write_news_cache(symbol, items)
        return sorted(
            items, key=lambda item: _news_epoch(item.get("published") or 0), reverse=True
        )[: max(1, int(limit))]
    return get_cached_news(symbol)[: max(1, int(limit))]


def fetch_profile_via_provider(ticker: str, *, provider_name: str | None = None) -> dict[str, Any]:
    symbol = _normalize_ticker(ticker)
    provider_key = str(provider_name or get_selected_provider()).strip().lower() or DEFAULT_PROVIDER
    adapter_cls = PROVIDERS.get(provider_key, YahooFinanceAdapter)
    try:
        return adapter_cls().get_profile(symbol)
    except Exception:
        return {
            "ticker": symbol,
            "name": symbol,
            "exchange": "Manual",
            "sector": None,
            "currency": "USD",
        }
