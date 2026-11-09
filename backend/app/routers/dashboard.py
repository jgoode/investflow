from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.dashboard import get_dashboard_payload

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return get_dashboard_payload()
