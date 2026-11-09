from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.reports import export_report, run_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{kind}")
def get_report(kind: str, request: Request) -> dict[str, Any]:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    params: dict[str, Any] = {}
    for key in request.query_params:
        params[key] = request.query_params.get(key)
    return {"report": run_report(kind, params)}


@router.get("/{kind}/xlsx")
def get_report_xlsx(kind: str, request: Request) -> Response:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    params: dict[str, Any] = {}
    for key in request.query_params:
        params[key] = request.query_params.get(key)
    payload, filename = export_report(kind, params, "xlsx")
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{kind}/pdf")
def get_report_pdf(kind: str, request: Request) -> Response:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    params: dict[str, Any] = {}
    for key in request.query_params:
        params[key] = request.query_params.get(key)
    payload, filename = export_report(kind, params, "pdf")
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{kind}/export")
def get_report_export(kind: str, request: Request, format: str = "xlsx") -> Response:
    if not getattr(request.state, "current_user", None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    params: dict[str, Any] = {}
    for key in request.query_params:
        if key != "format":
            params[key] = request.query_params.get(key)
    payload, filename = export_report(kind, params, format)
    media_type = (
        "application/pdf" if str(format).lower() == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
