"""Settings routes (FR-S / ITER-16)."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import UTC, datetime
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from app.accounts import ensure_seeded_coa
from app.db.connection import connect, resolve_db_path
from app.providers import read_setting, write_setting
from app.transactions import ensure_transactions_tables

router = APIRouter(prefix="/api", tags=["settings"])

DEFAULT_SETTINGS: dict[str, object] = {
    "currency": "USD",
    "provider.selected": "yahoo",
    "posting.default_window_days": 0,
    "ui.first_day_of_week": "monday",
    "ui.rounding_mode": "round-half-up",
    "profile.display_name": "",
}


class SettingsPatchPayload(BaseModel):
    settings: dict[str, object] | None = None
    updates: list[dict[str, object]] | None = None
    key: str | None = None
    value: object | None = None


def _current_user_id(request: Request) -> int:
    current_user = getattr(request.state, "current_user", None)
    if not isinstance(current_user, dict) or "id" not in current_user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return int(current_user["id"])


def _coerce_csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _detect_value_type(value: object) -> str:
    if value is None:
        return "str"
    if isinstance(value, (dict, list, tuple, set)):
        return "json"
    if isinstance(value, (bool, int, float)):
        return "json"
    return "str"


def _ensure_default_settings() -> dict[str, object]:
    settings = {}
    for key, default in DEFAULT_SETTINGS.items():
        current = read_setting(key, default)
        if current is None:
            write_setting(key, default, value_type=_detect_value_type(default))
            current = default
        settings[key] = current
    return settings


def _read_settings_map() -> dict[str, object]:
    _ensure_default_settings()
    with connect() as conn:
        rows = conn.execute(
            "SELECT key, value, value_type FROM settings ORDER BY key ASC"
        ).fetchall()
    settings: dict[str, object] = {}
    for row in rows:
        key = str(row["key"])
        value = row["value"]
        value_type = str(row["value_type"] or "str")
        if value is None:
            settings[key] = None
            continue
        if value_type == "json":
            try:
                settings[key] = json.loads(value)
            except json.JSONDecodeError:
                settings[key] = value
        else:
            settings[key] = value
    return {**DEFAULT_SETTINGS, **settings}


def _write_single_setting(key: str, value: object) -> object:
    if not key or not isinstance(key, str):
        raise HTTPException(status_code=422, detail="setting key is required")
    write_setting(key, value, value_type=_detect_value_type(value))
    return _read_settings_map().get(key)


def _record_settings_audit(user_id: int, summary: str) -> None:
    ensure_transactions_tables()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (user_id, action, entity, entity_id, summary, created_at)
            VALUES (?, 'settings.update', 'settings', NULL, ?, ?)
            """,
            (user_id, summary, int(time.time())),
        )
        conn.commit()


@router.get("/settings")
def list_settings(request: Request) -> dict[str, object]:
    _current_user_id(request)
    settings = _read_settings_map()
    return {
        "settings": settings,
        "keys": sorted(settings.keys()),
        "meta": {
            "currency": settings.get("currency", "USD"),
            "provider": settings.get("provider.selected", "yahoo"),
        },
    }


@router.patch("/settings")
def patch_settings(payload: SettingsPatchPayload, request: Request) -> dict[str, object]:
    user_id = _current_user_id(request)
    updates: dict[str, object] = {}
    if payload.settings is not None:
        updates.update(payload.settings)
    if payload.updates is not None:
        for item in payload.updates:
            if not isinstance(item, dict):
                raise HTTPException(status_code=422, detail="invalid setting update")
            key = item.get("key")
            if not isinstance(key, str) or not key:
                raise HTTPException(status_code=422, detail="setting key is required")
            updates[key] = item.get("value")
    if payload.key is not None:
        updates[payload.key] = payload.value
    if not updates:
        raise HTTPException(status_code=422, detail="no settings provided")
    for key, value in updates.items():
        _write_single_setting(key, value)
    _record_settings_audit(user_id, f"updated {len(updates)} settings")
    return {"settings": _read_settings_map()}


@router.get("/settings/seed")
def get_seed_status(request: Request) -> dict[str, object]:
    _current_user_id(request)
    ensure_seeded_coa()
    with connect() as conn:
        row = conn.execute(
            "SELECT name, version, applied_at FROM seed_meta WHERE name = 'coa_v1' LIMIT 1"
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="seed metadata unavailable")
    return {
        "seed": {
            "name": row["name"],
            "version": int(row["version"]),
            "applied_at": int(row["applied_at"]),
        }
    }


@router.post("/settings/seed/apply")
def apply_seed(request: Request) -> dict[str, str]:
    user_id = _current_user_id(request)
    ensure_seeded_coa()
    _record_settings_audit(user_id, "applied seed coa_v1")
    return {"status": "ok"}


@router.get("/settings/backup")
def export_backup(request: Request) -> FileResponse:
    _current_user_id(request)
    db_path = resolve_db_path()
    stamp = int(time.time())
    temp_path = NamedTemporaryFile(prefix="investflow-backup-", suffix=".db", delete=False)
    temp_path.close()
    try:
        with sqlite3.connect(db_path) as source, sqlite3.connect(temp_path.name) as target:
            source.backup(target)
        return FileResponse(
            temp_path.name,
            media_type="application/octet-stream",
            filename=f"investflow-backup-{stamp}.db",
            background=BackgroundTask(
                lambda: os.remove(temp_path.name) if os.path.exists(temp_path.name) else None
            ),
        )
    except Exception:
        if os.path.exists(temp_path.name):
            os.remove(temp_path.name)
        raise


@router.get("/audit")
def audit_log(request: Request) -> dict[str, object]:
    _current_user_id(request)
    ensure_transactions_tables()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.user_id, u.username, a.action, a.entity, a.entity_id,
                   a.summary, a.created_at
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT 100
            """
        ).fetchall()
    items = []
    for row in rows:
        created = int(row["created_at"])
        items.append(
            {
                "id": int(row["id"]),
                "user_id": row["user_id"],
                "username": row["username"],
                "action": row["action"],
                "entity": row["entity"],
                "entity_id": row["entity_id"],
                "summary": row["summary"],
                "created_at": created,
                "created_at_iso": datetime.fromtimestamp(created, tz=UTC).isoformat(),
            }
        )
    return {"items": items, "count": len(items)}
