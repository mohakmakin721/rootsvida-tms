"""Auth endpoints — login, whoami, and (owner-only) user creation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_org_id, current_user, require_role
from app.db import get_session
from app.models import User
from app.models.enums import UserRole
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_require_owner = require_role(UserRole.OWNER)


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None
    role: UserRole
    is_active: bool


class LoginOut(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreateIn(BaseModel):
    email: str
    password: str
    name: str | None = None
    role: UserRole = UserRole.READONLY


class UserUpdateIn(BaseModel):
    role: UserRole | None = None
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
    return LoginOut(token=auth_service.token_for(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


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
    _owner: User = Depends(_require_owner),
) -> None:
    """Owner resets a teammate's password (no current password needed)."""
    target = session.scalar(select(User).where(User.id == user_id, User.org_id == org_id))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    auth_service.set_password(session, target, body.new_password)


@router.get("/users", response_model=list[UserOut])
def list_users(
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _owner: User = Depends(_require_owner),
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
    _owner: User = Depends(_require_owner),
) -> User:
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
    owner: User = Depends(_require_owner),
) -> User:
    """Change a user's role or activation. Owner-only. You cannot demote or
    deactivate yourself — that guards against locking the org out of ownership."""
    user = session.scalar(select(User).where(User.id == user_id, User.org_id == org_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.id == owner.id and (
        (body.role is not None and body.role is not UserRole.OWNER) or body.is_active is False
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="you cannot change your own role or deactivate yourself",
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
    owner: User = Depends(_require_owner),
) -> None:
    """Remove a user (soft delete — the account can no longer log in and drops off
    the list). Owner-only. You cannot delete yourself, and you cannot delete the
    last remaining owner (that would lock the org out of user management)."""
    user = session.scalar(
        select(User).where(
            User.id == user_id, User.org_id == org_id, User.deleted_at.is_(None)
        )
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.id == owner.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="you cannot delete yourself"
        )
    if user.role is UserRole.OWNER:
        other_owners = session.scalar(
            select(func.count()).where(
                User.org_id == org_id,
                User.role == UserRole.OWNER,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
                User.id != user.id,
            )
        )
        if not other_owners:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="cannot delete the last owner",
            )
    user.is_active = False
    user.deleted_at = datetime.now(UTC)
    session.flush()
