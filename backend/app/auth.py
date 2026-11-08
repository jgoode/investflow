"""Auth/session helpers for ITER-02."""

from __future__ import annotations

import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request, Response, status

from app.db.connection import connect

JWT_COOKIE_NAME = "investflow_session"
REGISTER_SESSION_COOKIE_NAME = "investflow_regsid"
CSRF_HEADER = "x-requested-with"
CSRF_HEADER_VALUE = "investflow"
JWT_ALGORITHM = "HS256"
JWT_HOURS = 12
REGISTER_LIMIT = 5
REGISTER_WINDOW_SECONDS = 10 * 60
LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60
GENERIC_LOGIN_FAILURE = "invalid username or password"


def now_ts() -> int:
    return int(time.time())


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def cookie_secure() -> bool:
    value = os.environ.get("INVESTFLOW_COOKIE_SECURE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def jwt_secret() -> str:
    configured = os.environ.get("INVESTFLOW_JWT_SECRET", "").strip()
    if configured:
        return configured
    return "investflow-dev-insecure-secret-32b"


def _normalize_username(username: str) -> str:
    return username.strip().lower()


password_hasher = PasswordHasher()
_dummy_hash = password_hasher.hash("timing-equalizer-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return bool(password_hasher.verify(password_hash, password))
    except (VerifyMismatchError, VerificationError):
        return False


def verify_password_timing_equal(candidate_hash: str | None, password: str) -> bool:
    password_hash = candidate_hash if candidate_hash else _dummy_hash
    return verify_password(password_hash, password)


@dataclass
class LoginThrottleState:
    failures: int = 0
    window_started_at: int = 0
    throttled_until: int = 0


class AuthRuntimeState:
    def __init__(self) -> None:
        self.login_failures: dict[str, LoginThrottleState] = defaultdict(LoginThrottleState)
        self.registration_times: dict[str, list[int]] = defaultdict(list)


def ensure_auth_state(request: Request) -> AuthRuntimeState:
    state = getattr(request.app.state, "auth_state", None)
    if isinstance(state, AuthRuntimeState):
        return state
    request.app.state.auth_state = AuthRuntimeState()
    return cast(AuthRuntimeState, request.app.state.auth_state)


def create_session_token(user_id: int, session_epoch: int) -> str:
    payload = {
        "sub": str(user_id),
        "session_epoch": session_epoch,
        "exp": utc_now() + timedelta(hours=JWT_HOURS),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> dict[str, Any]:
    try:
        decoded = jwt.decode(token, jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
        ) from exc
    if "sub" not in decoded or "session_epoch" not in decoded:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return decoded


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
        max_age=JWT_HOURS * 60 * 60,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=JWT_COOKIE_NAME, path="/")


def user_public_payload(user_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user_row["id"],
        "username": user_row["username"],
        "display_name": user_row["display_name"],
        "is_active": bool(user_row["is_active"]),
        "session_epoch": user_row["session_epoch"],
    }


def fetch_user_by_username(username: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, username, display_name, password_hash, is_active, session_epoch
            FROM users
            WHERE username = ?
            """,
            (_normalize_username(username),),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def fetch_user_by_id(user_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, username, display_name, password_hash, is_active, session_epoch
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def create_user(username: str, display_name: str | None, password: str) -> dict[str, Any]:
    username_normalized = _normalize_username(username)
    now = now_ts()
    password_hash = hash_password(password)
    with connect() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username,
                    display_name,
                    password_hash,
                    is_active,
                    session_epoch,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, 1, 1, ?, ?)
                """,
                (username_normalized, display_name, password_hash, now, now),
            )
            conn.commit()
        except Exception as exc:
            if "UNIQUE constraint failed: users.username" in str(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="username already taken",
                ) from exc
            raise
        if cursor.lastrowid is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="user create failed"
            )
        user_id = int(cursor.lastrowid)
    created = fetch_user_by_id(user_id)
    if created is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="user create failed"
        )
    return created


def ensure_csrf_for_mutation(request: Request) -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    provided = request.headers.get(CSRF_HEADER, "")
    if provided != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf check failed")


def _registration_key(request: Request) -> str:
    current = request.cookies.get(REGISTER_SESSION_COOKIE_NAME)
    if current:
        return current
    new_id = uuid.uuid4().hex
    request.state.register_session_id_to_set = new_id
    return new_id


def enforce_registration_limit(request: Request) -> None:
    auth_state = ensure_auth_state(request)
    key = _registration_key(request)
    now = now_ts()
    attempts = [
        ts for ts in auth_state.registration_times[key] if ts >= now - REGISTER_WINDOW_SECONDS
    ]
    auth_state.registration_times[key] = attempts
    if len(attempts) >= REGISTER_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many registrations"
        )


def record_registration_success(request: Request, response: Response) -> None:
    auth_state = ensure_auth_state(request)
    key = _registration_key(request)
    auth_state.registration_times[key].append(now_ts())
    session_id_to_set = getattr(request.state, "register_session_id_to_set", None)
    if isinstance(session_id_to_set, str):
        response.set_cookie(
            key=REGISTER_SESSION_COOKIE_NAME,
            value=session_id_to_set,
            httponly=True,
            secure=cookie_secure(),
            samesite="lax",
            path="/",
            max_age=30 * 24 * 60 * 60,
        )


def check_login_throttle(request: Request, username: str) -> None:
    auth_state = ensure_auth_state(request)
    state = auth_state.login_failures[_normalize_username(username)]
    now = now_ts()
    if state.throttled_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many login attempts"
        )
    if state.window_started_at and now - state.window_started_at > LOGIN_WINDOW_SECONDS:
        state.failures = 0
        state.window_started_at = 0
        state.throttled_until = 0


def record_login_failure(request: Request, username: str) -> None:
    auth_state = ensure_auth_state(request)
    state = auth_state.login_failures[_normalize_username(username)]
    now = now_ts()
    if not state.window_started_at or now - state.window_started_at > LOGIN_WINDOW_SECONDS:
        state.window_started_at = now
        state.failures = 0
        state.throttled_until = 0
    state.failures += 1
    if state.failures >= LOGIN_LIMIT:
        state.throttled_until = now + LOGIN_WINDOW_SECONDS


def reset_login_failures(request: Request, username: str) -> None:
    auth_state = ensure_auth_state(request)
    auth_state.login_failures[_normalize_username(username)] = LoginThrottleState()


def authenticate_request_cookie(request: Request) -> dict[str, Any]:
    token = request.cookies.get(JWT_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    payload = decode_session_token(token)
    user = fetch_user_by_id(int(payload["sub"]))
    if user is None or not bool(user["is_active"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    if int(payload["session_epoch"]) != int(user["session_epoch"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return user
