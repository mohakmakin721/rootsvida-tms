"""Phase 5 M5: itinerary_intakes.origin (travellers' start point)

Revision ID: 0020_intake_origin
Revises: 0019_intake_and_rate_pricing
Create Date: 2026-08-12

Transport planning needs the travellers' start point — a drive/flight from the
origin, airport pickup, etc. Add a nullable `origin` column to the intake.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_intake_origin"
down_revision: str | None = "0019_intake_and_rate_pricing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("itinerary_intakes", sa.Column("origin", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("itinerary_intakes", "origin")
