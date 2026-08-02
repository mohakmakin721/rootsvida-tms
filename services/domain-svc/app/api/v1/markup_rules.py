"""Markup-rule endpoints — the org's markup policy (e.g. Foreign 15%, Indian 10%)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id, require_permission
from app.db import get_session
from app.models import MarkupRule, TravellerSegment
from app.models.enums import MarkupBasis
from app.security.permissions import MARKUP_MANAGE

router = APIRouter(prefix="/markup-rules", tags=["markup"])

# Markup policy is commercial — gated on markup.manage.
_manage = require_permission(MARKUP_MANAGE)


class MarkupRuleIn(BaseModel):
    label: str
    basis: MarkupBasis = MarkupBasis.MARKUP_ON_COST
    rate: Decimal = Field(ge=0)
    is_default: bool = False


class MarkupRuleUpdate(BaseModel):
    label: str | None = None
    basis: MarkupBasis | None = None
    rate: Decimal | None = Field(default=None, ge=0)
    is_default: bool | None = None


class MarkupRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    basis: MarkupBasis
    rate: Decimal
    is_default: bool


def _require(session: Session, org_id: uuid.UUID, rule_id: uuid.UUID) -> MarkupRule:
    rule = session.scalar(
        select(MarkupRule).where(MarkupRule.id == rule_id, MarkupRule.org_id == org_id)
    )
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="markup rule not found")
    return rule


@router.post("", response_model=MarkupRuleOut, status_code=status.HTTP_201_CREATED)
def create_markup_rule(
    body: MarkupRuleIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> MarkupRule:
    rule = MarkupRule(org_id=org_id, **body.model_dump())
    session.add(rule)
    session.flush()
    return rule


@router.get("", response_model=list[MarkupRuleOut])
def list_markup_rules(
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[MarkupRule]:
    return list(
        session.scalars(
            select(MarkupRule).where(MarkupRule.org_id == org_id).order_by(MarkupRule.label)
        )
    )


@router.patch("/{rule_id}", response_model=MarkupRuleOut)
def update_markup_rule(
    rule_id: uuid.UUID,
    body: MarkupRuleUpdate,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> MarkupRule:
    rule = _require(session, org_id, rule_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    session.flush()
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_markup_rule(
    rule_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> None:
    rule = _require(session, org_id, rule_id)
    in_use = session.scalar(
        select(func.count()).select_from(TravellerSegment).where(
            TravellerSegment.markup_rule_id == rule_id
        )
    )
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"markup rule is used by {in_use} traveller group(s); reassign them first",
        )
    session.delete(rule)
    session.flush()
