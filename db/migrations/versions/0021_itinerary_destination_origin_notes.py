"""Phase 5 M6: itineraries.destination / origin / notes

Revision ID: 0021_itinerary_dest_origin_notes
Revises: 0020_intake_origin
Create Date: 2026-08-12

Destination, travellers' start point (origin), and free-text planning notes /
constraints become first-class fields on the itinerary — captured in the builder
intake, fed to the AI drafter, and saved on create/update.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_itinerary_dest_origin_notes"
down_revision: str | None = "0020_intake_origin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("itineraries", sa.Column("destination", sa.Text(), nullable=True))
    op.add_column("itineraries", sa.Column("origin", sa.Text(), nullable=True))
    op.add_column("itineraries", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("itineraries", "notes")
    op.drop_column("itineraries", "origin")
    op.drop_column("itineraries", "destination")
