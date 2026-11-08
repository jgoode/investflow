"""Auth routes (ITER-02)."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth import (
    GENERIC_LOGIN_FAILURE,
    authenticate_request_cookie,
    check_login_throttle,
    clear_session_cookie,
    create_session_token,
    create_user,
    enforce_registration_limit,
    fetch_user_by_username,
    record_login_failure,
    record_registration_success,
    reset_login_failures,
    set_session_cookie,
    user_public_payload,
    verify_password_timing_equal,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,32}$")


class RegisterPayload(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    display_name: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=10, max_length=256)
    password_confirmation: str = Field(min_length=10, max_length=256)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise ValueError("username must match ^[a-z0-9._-]+$")
        return value

    @model_validator(mode="after")
    def validate_password_constraints(self) -> RegisterPayload:
        if self.password != self.password_confirmation:
            raise ValueError("password confirmation mismatch")
        if self.username in self.password.lower():
            raise ValueError("password must not contain username")
        return self


class LoginPayload(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=10, max_length=256)


@router.post("/register")
def register(payload: RegisterPayload, request: Request, response: Response) -> dict[str, object]:
    enforce_registration_limit(request)
    user = create_user(
        username=payload.username,
        display_name=payload.display_name,
        password=payload.password,
    )
    token = create_session_token(user_id=user["id"], session_epoch=user["session_epoch"])
    set_session_cookie(response, token)
    record_registration_success(request, response)
    return {"user": user_public_payload(user)}


@router.post("/login")
def login(payload: LoginPayload, request: Request, response: Response) -> dict[str, object]:
    check_login_throttle(request, payload.username)
    user = fetch_user_by_username(payload.username)
    password_ok = verify_password_timing_equal(
        user["password_hash"] if user else None, payload.password
    )
    user_is_valid = user is not None and password_ok and bool(user["is_active"])

    if not user_is_valid:
        record_login_failure(request, payload.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_FAILURE)

    assert user is not None
    reset_login_failures(request, payload.username)
    token = create_session_token(user_id=user["id"], session_epoch=user["session_epoch"])
    set_session_cookie(response, token)
    return {"user": user_public_payload(user)}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    authenticate_request_cookie(request)
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me")
def me(request: Request) -> dict[str, object]:
    user = authenticate_request_cookie(request)
    return {"user": user_public_payload(user)}
