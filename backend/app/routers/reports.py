from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.reports import run_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{kind}")
def get_report(kind: str, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    params: dict[str, Any] = {}
    for key in request.query_params:
        params[key] = request.query_params.get(key)
    return {"report": run_report(kind, params)}
