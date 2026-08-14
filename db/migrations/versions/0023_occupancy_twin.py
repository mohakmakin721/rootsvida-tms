"""Owner batch: add 'twin' to the occupancy enum (twin-bed stay rates)

Revision ID: 0023_occupancy_twin
Revises: 0022_normalize_stay_categories
Create Date: 2026-08-14

Adds a fifth occupancy — 'twin' (twin bed) — so hotel/stay rates can be quoted for a
twin room alongside single/double/triple/extra_adult. Additive and idempotent
(IF NOT EXISTS); PG 16 allows ADD VALUE inside the migration transaction since the
new value isn't used until a later transaction. Enum values can't be dropped, so
downgrade is a no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023_occupancy_twin"
down_revision: str | None = "0022_normalize_stay_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE occupancy ADD VALUE IF NOT EXISTS 'twin'")


def downgrade() -> None:
    # Postgres cannot remove a value from an enum type — nothing to undo.
    pass
