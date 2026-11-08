"""User-management routes (ITER-03)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator

from app.auth import (
    change_own_password,
    create_session_token,
    list_users,
    set_session_cookie,
    update_user_fields,
    user_public_payload,
)

router = APIRouter(prefix="/api/users", tags=["users"])


class UserUpdatePayload(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class PasswordChangePayload(BaseModel):
    old_password: str = Field(min_length=10, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)
    new_password_confirmation: str = Field(min_length=10, max_length=256)

    @model_validator(mode="after")
    def validate_password_confirmation(self) -> PasswordChangePayload:
        if self.new_password != self.new_password_confirmation:
            raise ValueError("password confirmation mismatch")
        return self


def _current_user_id(request: Request) -> int:
    current_user = getattr(request.state, "current_user", None)
    if not isinstance(current_user, dict) or "id" not in current_user:
        raise HTTPException(status_code=401, detail="unauthorized")
    return int(current_user["id"])


@router.get("")
def users_list() -> dict[str, object]:
    users = [user_public_payload(row) for row in list_users()]
    return {"users": users}


@router.patch("/{user_id}")
def users_update(user_id: int, payload: UserUpdatePayload, request: Request) -> dict[str, object]:
    actor_id = _current_user_id(request)
    updated = update_user_fields(
        actor_user_id=actor_id,
        target_user_id=user_id,
        display_name=payload.display_name,
        is_active=payload.is_active,
    )
    return {"user": user_public_payload(updated)}


@router.delete("/{user_id}")
def users_delete(user_id: int, request: Request) -> dict[str, str]:
    actor_id = _current_user_id(request)
    update_user_fields(
        actor_user_id=actor_id,
        target_user_id=user_id,
        soft_delete=True,
    )
    return {"status": "ok"}


@router.patch("/me/password")
def users_change_password(
    payload: PasswordChangePayload,
    request: Request,
    response: Response,
) -> dict[str, object]:
    actor_id = _current_user_id(request)
    current_user = getattr(request.state, "current_user", None)
    if not isinstance(current_user, dict) or "username" not in current_user:
        raise HTTPException(status_code=401, detail="unauthorized")
    username = str(current_user["username"])
    if username in payload.new_password.lower():
        raise HTTPException(status_code=422, detail="password must not contain username")
    updated = change_own_password(
        user_id=actor_id,
        old_password=payload.old_password,
        new_password=payload.new_password,
    )
    token = create_session_token(user_id=updated["id"], session_epoch=updated["session_epoch"])
    set_session_cookie(response, token)
    return {"user": user_public_payload(updated)}
