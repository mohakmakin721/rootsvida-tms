"""Markup-rule endpoints — the org's markup policy (e.g. Foreign 15%, Indian 10%)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.models import MarkupRule
from app.models.enums import MarkupBasis

router = APIRouter(prefix="/markup-rules", tags=["markup"])


class MarkupRuleIn(BaseModel):
    label: str
    basis: MarkupBasis = MarkupBasis.MARKUP_ON_COST
    rate: Decimal = Field(ge=0)
    is_default: bool = False


class MarkupRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    basis: MarkupBasis
    rate: Decimal
    is_default: bool


@router.post("", response_model=MarkupRuleOut, status_code=status.HTTP_201_CREATED)
def create_markup_rule(
    body: MarkupRuleIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
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
    return list(session.scalars(select(MarkupRule).where(MarkupRule.org_id == org_id)))
