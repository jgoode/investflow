"""Import API (L2) — FR-IMP-1 portfolio CSV import.

Endpoints under /api/imports: preview, commit, starter templates, saved
column-mapping templates. All require an authenticated session (middleware
sets request.state.current_user); mutations additionally pass CSRF checks.
"""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.db.connection import connect
from app.services.importer import mapping
from app.services.importer.parser import ImportError as FileImportError
from app.services.importer.service import ensure_import_tables, run_commit, run_preview

router = APIRouter(prefix="/api/imports", tags=["imports"])


def _current_user_id(request: Request) -> int:
    user = getattr(request.state, "current_user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return int(user["id"])


@router.post("/preview")
def preview_import(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    user_id = _current_user_id(request)
    return run_preview(payload, user_id=user_id)


@router.post("/commit")
def commit_import(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    user_id = _current_user_id(request)
    return run_commit(payload, user_id=user_id)


@router.get("/templates")
def starter_templates(request: Request) -> dict[str, Any]:
    _current_user_id(request)
    with connect() as conn:
        account_rows = conn.execute(
            "SELECT id, name, type, subtype FROM accounts a "
            "WHERE is_archived = 0 "
            "AND NOT EXISTS (SELECT 1 FROM accounts c WHERE c.parent_id = a.id) "
            "ORDER BY name ASC"
        ).fetchall()
    accounts = [
        {
            "id": int(row["id"]),
            "name": row["name"],
            "type": row["type"],
            "subtype": row["subtype"],
        }
        for row in account_rows
    ]
    return {
        "templates": mapping.list_starter_templates(),
        "mappings": _list_mappings(),
        "accounts": accounts,
    }


def _list_mappings() -> list[dict[str, Any]]:
    ensure_import_tables()
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, kind, columns_json, created_at, updated_at "
            "FROM import_mappings ORDER BY name ASC"
        ).fetchall()
    entries = []
    for row in rows:
        try:
            columns = json.loads(row["columns_json"])
        except (TypeError, ValueError):
            columns = {}
        entries.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "kind": row["kind"],
                "column_mapping": columns,
                "created_at": int(row["created_at"]),
                "updated_at": int(row["updated_at"]),
            }
        )
    return entries


@router.get("/mappings")
def list_mappings(request: Request) -> dict[str, Any]:
    _current_user_id(request)
    return {"mappings": _list_mappings()}


@router.post("/mappings", status_code=201)
def create_mapping(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    user_id = _current_user_id(request)
    name = str(payload.get("name") or "").strip()
    kind = str(payload.get("kind") or "").strip()
    columns = payload.get("column_mapping")
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="mapping name is required",
        )
    if kind not in mapping.CANONICAL_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"unsupported import kind: {kind!r}",
        )
    if not isinstance(columns, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="column_mapping must be an object of {field: csv column title}",
        )
    try:
        mapping.resolve_mapping(kind, columns)
    except FileImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    now = int(time.time())
    ensure_import_tables()
    with connect() as conn:
        existing = conn.execute("SELECT id FROM import_mappings WHERE name = ?", (name,)).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"a mapping named {name!r} already exists",
            )
        cursor = conn.execute(
            """
            INSERT INTO import_mappings
                (name, kind, columns_json, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, kind, json.dumps(columns), user_id, now, now),
        )
        created_id = cursor.lastrowid
        if created_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="mapping insertion failed",
            )
        mapping_id = int(created_id)
        conn.commit()
    return {
        "mapping": {
            "id": mapping_id,
            "name": name,
            "kind": kind,
            "column_mapping": columns,
        }
    }


@router.delete("/mappings/{mapping_id}")
def delete_mapping(request: Request, mapping_id: int) -> dict[str, Any]:
    _current_user_id(request)
    ensure_import_tables()
    with connect() as conn:
        existing = conn.execute(
            "SELECT id, name FROM import_mappings WHERE id = ?", (mapping_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mapping not found")
        conn.execute("DELETE FROM import_mappings WHERE id = ?", (mapping_id,))
        conn.commit()
    return {"deleted": int(existing["id"]), "name": existing["name"]}
