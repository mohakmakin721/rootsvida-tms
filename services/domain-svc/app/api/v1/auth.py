"""Auth endpoints — login, whoami, and (owner-only) user creation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
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


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, session: Session = Depends(get_session)) -> LoginOut:
    user = auth_service.authenticate(session, str(body.email), body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return LoginOut(token=auth_service.token_for(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


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
