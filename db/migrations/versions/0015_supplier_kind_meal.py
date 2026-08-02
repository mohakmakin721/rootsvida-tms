"""add 'meal' to the supplier_kind enum (vendor types, #3 groundwork)

Revision ID: 0015_supplier_kind_meal
Revises: 0014_dynamic_roles
Create Date: 2026-08-02

Vendors come in types (hotel, transport, guide, activity, meal, …). Meals were the
one common vendor type missing from `supplier_kind`. PostgreSQL 12+ allows ADD VALUE
inside a transaction (the new value just can't be *used* in the same transaction),
so this is safe under Alembic's transactional DDL. Enum values can't be dropped in
place, so downgrade is a no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015_supplier_kind_meal"
down_revision: str | None = "0014_dynamic_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE supplier_kind ADD VALUE IF NOT EXISTS 'meal'")


def downgrade() -> None:
    # PostgreSQL can't drop an enum value in place; leaving 'meal' is harmless.
    pass
