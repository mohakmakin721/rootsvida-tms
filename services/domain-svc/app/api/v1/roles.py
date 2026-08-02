"""Role & permission management (D-0015) — the owner-facing RBAC surface.

Gated on users.manage. Lists the permission catalog and the org's roles (with a
live user count each), and lets an admin create custom roles, edit any role's
label/description/permissions, and delete unused custom roles. Two invariants are
enforced here so the org can never be locked out or left in a broken state:
  * the owner role's permissions can't be reduced (it always holds every one);
  * a system role can't be deleted, and no role can be deleted while users hold it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id, require_permission
from app.db import get_session
from app.models import Role, User
from app.models.enums import UserRole
from app.security.permissions import ALL_PERMISSION_KEYS, PERMISSIONS, USERS_MANAGE
from app.services import roles as roles_service

router = APIRouter(prefix="/roles", tags=["roles"])

_require_admin = require_permission(USERS_MANAGE)
_OWNER = UserRole.OWNER.value


class PermissionOut(BaseModel):
    key: str
    label: str
    description: str
    group: str


class RoleOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    description: str | None
    is_system: bool
    permissions: list[str]
    user_count: int


class RoleCreateIn(BaseModel):
    label: str = Field(min_length=1)
    description: str | None = None
    permissions: list[str] = []


class RoleUpdateIn(BaseModel):
    label: str | None = Field(default=None, min_length=1)
    description: str | None = None
    permissions: list[str] | None = None


def _validate_permissions(perms: list[str]) -> list[str]:
    unknown = sorted(set(perms) - ALL_PERMISSION_KEYS)
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown permission(s): {unknown}",
        )
    return sorted(set(perms))


def _require_role(session: Session, org_id: uuid.UUID, role_id: uuid.UUID) -> Role:
    role = session.scalar(select(Role).where(Role.id == role_id, Role.org_id == org_id))
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="role not found")
    return role


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(_admin: User = Depends(_require_admin)) -> list[PermissionOut]:
    """The fixed permission catalog — the toggles the roles UI offers."""
    return [PermissionOut(**vars(p)) for p in PERMISSIONS]


@router.get("", response_model=list[RoleOut])
def list_roles(
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _admin: User = Depends(_require_admin),
) -> list[RoleOut]:
    return [RoleOut(**r) for r in roles_service.list_roles(session, org_id)]


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    body: RoleCreateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _admin: User = Depends(_require_admin),
) -> RoleOut:
    perms = _validate_permissions(body.permissions)
    key = roles_service.slugify_key(body.label)
    if session.scalar(select(Role.id).where(Role.org_id == org_id, Role.key == key)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"a role with key {key!r} already exists"
        )
    role = Role(
        org_id=org_id, key=key, label=body.label.strip(), description=body.description,
        is_system=False, permissions=perms,
    )
    session.add(role)
    session.flush()
    return _out(session, org_id, role)


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: uuid.UUID,
    body: RoleUpdateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _admin: User = Depends(_require_admin),
) -> RoleOut:
    role = _require_role(session, org_id, role_id)
    if body.label is not None:
        role.label = body.label.strip()
    if body.description is not None:
        role.description = body.description
    if body.permissions is not None:
        perms = _validate_permissions(body.permissions)
        # The owner role always holds every permission — its set can't be reduced.
        if role.key == _OWNER and set(perms) != ALL_PERMISSION_KEYS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="the owner role must keep every permission",
            )
        role.permissions = perms
    session.flush()
    return _out(session, org_id, role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _admin: User = Depends(_require_admin),
) -> None:
    role = _require_role(session, org_id, role_id)
    if role.is_system:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="built-in roles can't be deleted"
        )
    in_use = session.scalar(
        select(func.count()).where(
            User.org_id == org_id, User.role == role.key, User.deleted_at.is_(None)
        )
    ) or 0
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"{in_use} user(s) still have this role — reassign them first",
        )
    session.delete(role)
    session.flush()


def _out(session: Session, org_id: uuid.UUID, role: Role) -> RoleOut:
    count = session.scalar(
        select(func.count()).where(
            User.org_id == org_id, User.role == role.key, User.deleted_at.is_(None)
        )
    ) or 0
    return RoleOut(
        id=role.id, key=role.key, label=role.label, description=role.description,
        is_system=role.is_system, permissions=list(role.permissions or []),
        user_count=count,
    )
