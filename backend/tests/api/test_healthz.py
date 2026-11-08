"""L2 API test — GET /api/healthz (ITER-01 deliverable #2).

NFR-2 explicitly exempts /api/healthz from authentication.
"""

from fastapi.testclient import TestClient

from app.main import create_app
from app.version import __version__


def test_healthz_returns_ok_with_version() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/healthz")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_healthz_works_without_auth() -> None:
    """No session cookie exists in this client → still 200 (NFR-2 exemption)."""
    client = TestClient(create_app())  # never sets a session/cookie
    resp = client.get("/api/healthz")

    assert resp.status_code == 200
