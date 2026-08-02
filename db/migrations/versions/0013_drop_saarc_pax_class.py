"""drop 'saarc' from the pax_class enum (owner decision, 2026-08)

Revision ID: 0013_drop_saarc_pax_class
Revises: 0012_invoices
Create Date: 2026-08-02

Only Indian and Foreign traveller classes are used. PostgreSQL cannot drop a
value from an enum in place, so we recreate the type without 'saarc' and swap the
three columns that use it (`activity_rates.pax_class`, `traveller_segments.pax_class`,
`itinerary_components.applies_to_pax_class`) over via a text round-trip. The cast
fails loudly if any row still holds 'saarc' — by design; none should exist.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_drop_saarc_pax_class"
down_revision: str | None = "0012_invoices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column) pairs that use the pax_class enum.
_COLUMNS = [
    ("activity_rates", "pax_class"),
    ("traveller_segments", "pax_class"),
    ("itinerary_components", "applies_to_pax_class"),
]


def _swap_enum(values: tuple[str, ...]) -> None:
    quoted = ", ".join(f"'{v}'" for v in values)
    op.execute("ALTER TYPE pax_class RENAME TO pax_class_old")
    op.execute(f"CREATE TYPE pax_class AS ENUM ({quoted})")
    for table, column in _COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE pax_class "
            f"USING {column}::text::pax_class"
        )
    op.execute("DROP TYPE pax_class_old")


def upgrade() -> None:
    _swap_enum(("indian", "foreign"))


def downgrade() -> None:
    _swap_enum(("indian", "foreign", "saarc"))
