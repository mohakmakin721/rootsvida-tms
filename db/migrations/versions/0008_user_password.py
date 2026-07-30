"""auth: users.password_hash

Revision ID: 0008_user_password
Revises: 0007_itineraries_quotes
Create Date: 2026-07-30

Adds the password hash for self-hosted auth (D-0014). Nullable — existing users
and non-login service accounts have no password until one is set.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_user_password"
down_revision: str | None = "0007_itineraries_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
