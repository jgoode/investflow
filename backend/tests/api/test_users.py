"""L2 API tests — user management (FR-U4 / ITER-03)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CSRF_HEADER, login, register


def test_users_list_requires_authentication(client: TestClient) -> None:
    resp = client.get("/api/users")
    assert resp.status_code == 401


def test_users_list_returns_all_users_for_authenticated_user(client: TestClient) -> None:
    register(client, "alice")
    client.post("/api/auth/logout", headers=CSRF_HEADER)
    register(client, "bob")

    login(client, "alice")
    resp = client.get("/api/users")

    assert resp.status_code == 200
    payload = resp.json()["users"]
    usernames = {row["username"] for row in payload}
    assert usernames == {"alice", "bob"}
    assert {"created_at", "last_login_at", "is_active", "display_name"} <= payload[0].keys()


def test_users_edit_display_name(client: TestClient) -> None:
    register(client, "alice")
    client.post("/api/auth/logout", headers=CSRF_HEADER)
    register(client, "bob")

    login(client, "alice")
    users_resp = client.get("/api/users")
    bob_id = next(row["id"] for row in users_resp.json()["users"] if row["username"] == "bob")

    update = client.patch(
        f"/api/users/{bob_id}",
        headers=CSRF_HEADER,
        json={"display_name": "Bobby Tables"},
    )
    assert update.status_code == 200
    assert update.json()["user"]["display_name"] == "Bobby Tables"


def test_deactivate_user_revokes_existing_session_on_next_request(client: TestClient) -> None:
    register(client, "alice")
    client.post("/api/auth/logout", headers=CSRF_HEADER)
    register(client, "bob")
    client.post("/api/auth/logout", headers=CSRF_HEADER)

    login(client, "bob")
    bob_me = client.get("/api/auth/me")
    assert bob_me.status_code == 200
    bob_id = bob_me.json()["user"]["id"]
    client.post("/api/auth/logout", headers=CSRF_HEADER)

    login(client, "alice")
    deactivate = client.patch(
        f"/api/users/{bob_id}",
        headers=CSRF_HEADER,
        json={"is_active": False},
    )
    assert deactivate.status_code == 200

    client.post("/api/auth/logout", headers=CSRF_HEADER)
    login(client, "bob")
    assert client.get("/api/auth/me").status_code == 401


def test_last_active_user_cannot_be_deactivated_or_deleted(client: TestClient) -> None:
    register(client, "alice")
    me = client.get("/api/auth/me")
    alice_id = me.json()["user"]["id"]

    deactivate = client.patch(
        f"/api/users/{alice_id}",
        headers=CSRF_HEADER,
        json={"is_active": False},
    )
    assert deactivate.status_code == 409
    assert "last active" in deactivate.json()["detail"].lower()

    delete = client.delete(
        f"/api/users/{alice_id}",
        headers=CSRF_HEADER,
    )
    assert delete.status_code == 409
    assert "last active" in delete.json()["detail"].lower()


def test_user_cannot_deactivate_or_delete_self_even_when_not_last_active(
    client: TestClient,
) -> None:
    register(client, "alice")
    client.post("/api/auth/logout", headers=CSRF_HEADER)
    register(client, "bob")
    client.post("/api/auth/logout", headers=CSRF_HEADER)
    login(client, "alice")
    me = client.get("/api/auth/me")
    alice_id = me.json()["user"]["id"]

    deactivate = client.patch(
        f"/api/users/{alice_id}",
        headers=CSRF_HEADER,
        json={"is_active": False},
    )
    assert deactivate.status_code == 403

    delete = client.delete(
        f"/api/users/{alice_id}",
        headers=CSRF_HEADER,
    )
    assert delete.status_code == 403


def test_delete_endpoint_soft_deletes_user_and_blocks_login(client: TestClient) -> None:
    register(client, "alice")
    client.post("/api/auth/logout", headers=CSRF_HEADER)
    register(client, "bob")
    client.post("/api/auth/logout", headers=CSRF_HEADER)

    login(client, "alice")
    users_resp = client.get("/api/users")
    bob_id = next(row["id"] for row in users_resp.json()["users"] if row["username"] == "bob")

    delete = client.delete(f"/api/users/{bob_id}", headers=CSRF_HEADER)
    assert delete.status_code == 200
    assert delete.json()["status"] == "ok"

    users_after = client.get("/api/users").json()["users"]
    bob_after = next(row for row in users_after if row["id"] == bob_id)
    assert bob_after["is_active"] is False

    client.post("/api/auth/logout", headers=CSRF_HEADER)
    failed_login = login(client, "bob")
    assert failed_login.status_code == 401
    assert failed_login.json()["detail"] == "invalid username or password"


def test_change_own_password_requires_old_password_and_refreshes_session(
    client: TestClient,
) -> None:
    register(client, "alice", "correct-horse-10")

    wrong_old = client.patch(
        "/api/users/me/password",
        headers=CSRF_HEADER,
        json={
            "old_password": "incorrect-old-pass",
            "new_password": "new-secure-pass-22",
            "new_password_confirmation": "new-secure-pass-22",
        },
    )
    assert wrong_old.status_code == 401
    assert wrong_old.json()["detail"] == "invalid username or password"

    good = client.patch(
        "/api/users/me/password",
        headers=CSRF_HEADER,
        json={
            "old_password": "correct-horse-10",
            "new_password": "new-secure-pass-22",
            "new_password_confirmation": "new-secure-pass-22",
        },
    )
    assert good.status_code == 200
    assert "investflow_session=" in good.headers["set-cookie"]

    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout", headers=CSRF_HEADER)
    assert login(client, "alice", "correct-horse-10").status_code == 401
    assert login(client, "alice", "new-secure-pass-22").status_code == 200
