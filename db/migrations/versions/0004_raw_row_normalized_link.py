"""staging->canonical link: raw_import_rows.normalized_supplier_id

Revision ID: 0004_raw_row_link
Revises: 0003_provenance
Create Date: 2026-07-30

Adds the forward-provenance / idempotency link used by the migration step
(Milestone 6): the canonical supplier a staged row normalised to. Nullable — a
row may be unmapped (needs review) or not yet migrated. FK to suppliers with an
index for the reverse lookup ("which staged row produced this supplier").
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_raw_row_link"
down_revision: str | None = "0003_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "raw_import_rows",
        sa.Column("normalized_supplier_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_raw_import_rows_normalized_supplier_id_suppliers",
        "raw_import_rows",
        "suppliers",
        ["normalized_supplier_id"],
        ["id"],
    )
    op.create_index(
        "ix_raw_import_rows_normalized_supplier_id",
        "raw_import_rows",
        ["normalized_supplier_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_import_rows_normalized_supplier_id", "raw_import_rows")
    op.drop_constraint(
        "fk_raw_import_rows_normalized_supplier_id_suppliers",
        "raw_import_rows",
        type_="foreignkey",
    )
    op.drop_column("raw_import_rows", "normalized_supplier_id")
