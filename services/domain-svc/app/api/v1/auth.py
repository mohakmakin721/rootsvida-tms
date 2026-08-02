"""Auth endpoints — login, whoami, and (owner-only) user creation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_org_id, current_user, require_permission
from app.db import get_session
from app.models import Role, User
from app.models.enums import UserRole
from app.security.permissions import USERS_MANAGE
from app.services import auth as auth_service
from app.services import roles as roles_service

router = APIRouter(prefix="/auth", tags=["auth"])

_require_user_admin = require_permission(USERS_MANAGE)


def _require_role_key(session: Session, org_id: uuid.UUID, key: str) -> None:
    """422 if `key` is not an existing role in this org."""
    exists = session.scalar(select(Role.id).where(Role.org_id == org_id, Role.key == key))
    if exists is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"unknown role {key!r}"
        )


def _user_out(session: Session, user: User) -> UserOut:
    """UserOut with the caller's resolved permissions filled in (for /me + login)."""
    perms = sorted(roles_service.permissions_for_role(session, user.org_id, user.role))
    return UserOut(
        id=user.id, email=user.email, name=user.name, role=user.role,
        is_active=user.is_active, permissions=perms,
    )


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None
    role: str
    is_active: bool
    permissions: list[str] = []


class LoginOut(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreateIn(BaseModel):
    email: str
    password: str
    name: str | None = None
    role: str = UserRole.READONLY.value


class UserUpdateIn(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=6)


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, session: Session = Depends(get_session)) -> LoginOut:
    user = auth_service.authenticate(session, str(body.email), body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return LoginOut(token=auth_service.token_for(user), user=_user_out(session, user))


@router.get("/me", response_model=UserOut)
def me(
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> UserOut:
    return _user_out(session, user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordIn,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> None:
    """Change your own password (verifies the current one)."""
    if not auth_service.change_password(session, user, body.current_password, body.new_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="current password is incorrect")


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: uuid.UUID,
    body: ResetPasswordIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _admin: User = Depends(_require_user_admin),
) -> None:
    """Reset a teammate's password (no current password needed). Needs users.manage."""
    target = session.scalar(select(User).where(
        User.id == user_id, User.org_id == org_id, User.deleted_at.is_(None)
    ))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    auth_service.set_password(session, target, body.new_password)


@router.get("/users", response_model=list[UserOut])
def list_users(
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _admin: User = Depends(_require_user_admin),
) -> list[User]:
    return list(session.scalars(
        select(User)
        .where(User.org_id == org_id, User.deleted_at.is_(None))
        .order_by(User.email)
    ))


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _admin: User = Depends(_require_user_admin),
) -> User:
    _require_role_key(session, org_id, body.role)
    try:
        return auth_service.create_user(
            session, org_id, email=str(body.email), password=body.password,
            role=body.role, name=body.name,
        )
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="email already exists") from None


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    caller: User = Depends(_require_user_admin),
) -> User:
    """Change a user's role or activation (needs users.manage). You cannot change
    your own role or deactivate yourself, and you cannot demote/deactivate the last
    user who can manage users — both guard against locking the org out."""
    user = session.scalar(select(User).where(
        User.id == user_id, User.org_id == org_id, User.deleted_at.is_(None)
    ))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    if body.role is not None:
        _require_role_key(session, org_id, body.role)
    if user.id == caller.id and (
        (body.role is not None and body.role != user.role) or body.is_active is False
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="you cannot change your own role or deactivate yourself",
        )
    admin_keys = roles_service.admin_role_keys(session, org_id)
    losing_admin = user.role in admin_keys and (
        (body.role is not None and body.role not in admin_keys) or body.is_active is False
    )
    if losing_admin and roles_service.remaining_admin_count(
        session, org_id, excluding_user_id=user.id
    ) == 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="this is the last user who can manage users",
        )
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    session.flush()
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    caller: User = Depends(_require_user_admin),
) -> None:
    """Remove a user (soft delete — the account can no longer log in and drops off
    the list). Needs users.manage. You cannot delete yourself, and you cannot delete
    the last user who can manage users (that would lock the org out)."""
    user = session.scalar(
        select(User).where(
            User.id == user_id, User.org_id == org_id, User.deleted_at.is_(None)
        )
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.id == caller.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="you cannot delete yourself"
        )
    if user.role in roles_service.admin_role_keys(session, org_id) and (
        roles_service.remaining_admin_count(session, org_id, excluding_user_id=user.id) == 0
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="cannot delete the last user who can manage users",
        )
    user.is_active = False
    user.deleted_at = datetime.now(UTC)
    session.flush()
