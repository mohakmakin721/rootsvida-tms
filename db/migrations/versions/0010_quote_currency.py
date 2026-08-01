"""quotes: fx_currency (multi-currency quotations)

Revision ID: 0010_quote_currency
Revises: 0009_clients
Create Date: 2026-08-01

Adds `quotes.fx_currency` (Phase 3 M9) so a saved quote records the client-facing
currency it was priced in, not just an implied USD. Nullable — existing quotes keep
NULL (they were USD by convention). ₹ remains the authoritative money (D-0001);
`fx_rate_inr_usd` holds INR per one unit of `fx_currency`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_quote_currency"
down_revision: str | None = "0009_clients"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("fx_currency", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("quotes", "fx_currency")
