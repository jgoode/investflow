"""L2 API tests — settings surface (FR-S / ITER-16)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, login, register


def test_settings_round_trip_and_audit_log(client: TestClient) -> None:
    register(client, "alice")
    login(client, "alice")

    patch = client.patch(
        "/api/settings",
        headers=CSRF_HEADER,
        json={
            "settings": {
                "profile.display_name": "Alice Story",
                "provider.selected": "manual",
                "posting.default_window_days": 7,
                "currency": "USD",
            }
        },
    )
    assert patch.status_code == 200
    payload = patch.json()["settings"]
    assert payload["profile.display_name"] == "Alice Story"
    assert payload["provider.selected"] == "manual"
    assert payload["posting.default_window_days"] == 7

    refreshed = client.get("/api/settings")
    assert refreshed.status_code == 200
    assert refreshed.json()["settings"]["profile.display_name"] == "Alice Story"

    audit = client.get("/api/audit")
    assert audit.status_code == 200
    items = audit.json()["items"]
    assert any(item["action"] == "settings.update" for item in items)


def test_settings_accepts_single_key_and_list_updates(client: TestClient) -> None:
    register(client, "alice")
    login(client, "alice")

    single = client.patch(
        "/api/settings",
        headers=CSRF_HEADER,
        json={"key": "ui.first_day_of_week", "value": "sunday"},
    )
    assert single.status_code == 200
    assert single.json()["settings"]["ui.first_day_of_week"] == "sunday"

    list_update = client.patch(
        "/api/settings",
        headers=CSRF_HEADER,
        json={"updates": [{"key": "provider.selected", "value": "manual"}]},
    )
    assert list_update.status_code == 200
    assert list_update.json()["settings"]["provider.selected"] == "manual"

    invalid = client.patch(
        "/api/settings",
        headers=CSRF_HEADER,
        json={"settings": {}},
    )
    assert invalid.status_code == 422
    assert "no settings" in invalid.json()["detail"].lower()


def test_seed_and_backup_helpers_are_available(client: TestClient) -> None:
    register(client, "alice")
    login(client, "alice")

    seed = client.get("/api/settings/seed")
    assert seed.status_code == 200
    assert seed.json()["seed"]["name"] == "coa_v1"

    apply = client.post("/api/settings/seed/apply", headers=CSRF_HEADER)
    assert apply.status_code == 200
    assert apply.json()["status"] == "ok"

    backup = client.get("/api/settings/backup")
    assert backup.status_code == 200
    assert backup.headers["content-type"].startswith("application/octet-stream")
