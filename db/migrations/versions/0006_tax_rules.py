"""place-of-supply: seller GST identity on organizations + tax_rules

Revision ID: 0006_tax_rules
Revises: 0005_review_queue
Create Date: 2026-07-30

Adds the GST place-of-supply rule set as data (Part 2 §1.4, D-0013):
  - seller GST identity columns on organizations (Uttarakhand / 05)
  - tax_rules: one row per PlaceOfSupply scenario (intra/inter/international)
    documenting the treatment + split rates. Seeded by scripts/seed_org.py.

Hand-written, mirroring the 0003/0005 enum pattern.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models import enums as e

revision: str = "0006_tax_rules"
down_revision: str | None = "0005_review_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(enum_cls: type, name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*[m.value for m in enum_cls], name=name, create_type=False)


place_of_supply = _enum(e.PlaceOfSupply, "place_of_supply")
gst_treatment = _enum(e.GstTreatment, "gst_treatment")
NEW_ENUMS = [place_of_supply, gst_treatment]

_ORG_COLS = ("gstin", "pan", "gst_state_code", "gst_state_name")


def upgrade() -> None:
    bind = op.get_bind()
    for en in NEW_ENUMS:
        en.create(bind, checkfirst=True)

    for col in _ORG_COLS:
        op.add_column("organizations", sa.Column(col, sa.Text(), nullable=True))

    op.create_table(
        "tax_rules",
        sa.Column("scenario", place_of_supply, nullable=False),
        sa.Column("treatment", gst_treatment, nullable=False),
        sa.Column("gst_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("cgst_rate", sa.Numeric(6, 4), server_default="0", nullable=False),
        sa.Column("sgst_rate", sa.Numeric(6, 4), server_default="0", nullable=False),
        sa.Column("igst_rate", sa.Numeric(6, 4), server_default="0", nullable=False),
        sa.Column("hsn", sa.Text(), nullable=True),
        sa.Column("rounding_policy", sa.Text(),
                  server_default="gross_nearest_100", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                  nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_tax_rules_org_id_organizations"),
        sa.PrimaryKeyConstraint("id", name="pk_tax_rules"),
        sa.UniqueConstraint("org_id", "scenario", name="uq_tax_rules_org_id"),
    )
    op.create_index("ix_tax_rules_org_id", "tax_rules", ["org_id"])


def downgrade() -> None:
    op.drop_table("tax_rules")
    for col in reversed(_ORG_COLS):
        op.drop_column("organizations", col)
    bind = op.get_bind()
    for en in NEW_ENUMS:
        en.drop(bind, checkfirst=True)
