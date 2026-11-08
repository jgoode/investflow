"""healthz router — the only unauthenticated endpoint of ITER-01 (NFR-2 exemption)."""

from fastapi import APIRouter

from app.version import __version__

router: APIRouter = APIRouter(tags=["ops"])


@router.get("/api/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe — no auth by design (NFR-2 exempt path)."""
    return {"status": "ok", "version": __version__}
