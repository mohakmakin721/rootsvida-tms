"""add clients.corporate_name (organisation name for corporate clients)

Revision ID: 0017_client_corporate_name
Revises: 0016_consolidate_supplier_kind
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_client_corporate_name"
down_revision: str | None = "0016_consolidate_supplier_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("corporate_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "corporate_name")
