"""consolidate supplier_kind to 7 vendor types aligned with ComponentKind

Revision ID: 0016_consolidate_supplier_kind
Revises: 0015_supplier_kind_meal
Create Date: 2026-08-03

Vendor kinds now match the itinerary component kinds exactly:
stay, transport, guide, activity, meal, permit, misc. Accommodation (hotel +
homestay) becomes 'stay'; facilitator + photographer fold into 'misc'. Postgres
can't drop enum values in place, so we recreate the type and remap existing rows
via a CASE in the USING clause.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016_consolidate_supplier_kind"
down_revision: str | None = "0015_supplier_kind_meal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "'stay', 'transport', 'guide', 'activity', 'meal', 'permit', 'misc'"
_OLD = (
    "'hotel', 'homestay', 'transport', 'guide', 'activity', 'facilitator', "
    "'photographer', 'permit', 'misc', 'meal'"
)

_MAP_UP = """
    CASE kind::text
        WHEN 'hotel' THEN 'stay'
        WHEN 'homestay' THEN 'stay'
        WHEN 'facilitator' THEN 'misc'
        WHEN 'photographer' THEN 'misc'
        ELSE kind::text
    END::supplier_kind
"""

# 'stay' has no single original value; map it to 'hotel' on downgrade.
_MAP_DOWN = """
    CASE kind::text
        WHEN 'stay' THEN 'hotel'
        ELSE kind::text
    END::supplier_kind
"""


def _swap(values: str, using: str) -> None:
    op.execute("ALTER TYPE supplier_kind RENAME TO supplier_kind_old")
    op.execute(f"CREATE TYPE supplier_kind AS ENUM ({values})")
    op.execute(f"ALTER TABLE suppliers ALTER COLUMN kind TYPE supplier_kind USING ({using})")
    op.execute("DROP TYPE supplier_kind_old")


def upgrade() -> None:
    _swap(_NEW, _MAP_UP)


def downgrade() -> None:
    _swap(_OLD, _MAP_DOWN)
