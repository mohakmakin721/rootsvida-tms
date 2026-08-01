"""invoices: gapless GST invoices + credit notes (immutable)

Revision ID: 0012_invoices
Revises: 0011_project_timeline
Create Date: 2026-08-02

Phase 4: the GST invoice. `document_counters` gives gapless per-(org, kind, FY)
numbering; `invoices` freezes the seller/buyer identity and the tax breakdown with
a CHECK that the parts reconcile to the total; `invoice_lines` itemises it. An
issued invoice is immutable by trigger (only → 'cancelled'); a correction is a
credit note. Same trigger pattern as the quotes immutability (0007).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_invoices"
down_revision: str | None = "0011_project_timeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

gst_treatment = postgresql.ENUM(
    "cgst_sgst", "igst", "export", name="gst_treatment", create_type=False
)

_IMMUTABLE_FN = """
CREATE OR REPLACE FUNCTION forbid_issued_invoice_update() RETURNS trigger AS $$
BEGIN
  -- The only permitted update is cancelling an issued invoice. Everything else
  -- (editing figures, un-cancelling) is forbidden — corrections are credit notes.
  IF NOT (OLD.status = 'issued' AND NEW.status = 'cancelled') THEN
    RAISE EXCEPTION
      'Invoice % is immutable; only issued→cancelled is allowed. Raise a credit note.',
      OLD.id;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "document_counters",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("fiscal_year", sa.Text(), nullable=False),
        sa.Column("last_number", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_document_counters_org_id_organizations"),
        sa.PrimaryKeyConstraint("id", name="pk_document_counters"),
        sa.UniqueConstraint("org_id", "kind", "fiscal_year", name="uq_document_counters_org_id"),
    )
    op.create_index("ix_document_counters_org_id", "document_counters", ["org_id"])

    op.create_table(
        "invoices",
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("fiscal_year", sa.Text(), nullable=False),
        sa.Column("serial", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), server_default="invoice", nullable=False),
        sa.Column("status", sa.Text(), server_default="issued", nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("quote_id", sa.UUID(), nullable=False),
        sa.Column("project_code", sa.Text(), nullable=True),
        sa.Column("credit_note_of_id", sa.UUID(), nullable=True),
        sa.Column("seller_name", sa.Text(), nullable=False),
        sa.Column("seller_gstin", sa.Text(), nullable=True),
        sa.Column("seller_pan", sa.Text(), nullable=True),
        sa.Column("seller_state_code", sa.Text(), nullable=True),
        sa.Column("seller_state_name", sa.Text(), nullable=True),
        sa.Column("seller_address", sa.Text(), nullable=True),
        sa.Column("buyer_name", sa.Text(), nullable=False),
        sa.Column("buyer_country", sa.Text(), nullable=True),
        sa.Column("buyer_gstin", sa.Text(), nullable=True),
        sa.Column("place_of_supply", sa.Text(), nullable=True),
        sa.Column("hsn", sa.Text(), nullable=True),
        sa.Column("gst_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("gst_treatment", gst_treatment, nullable=False),
        sa.Column("taxable", sa.Numeric(14, 2), nullable=False),
        sa.Column("cgst", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("sgst", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("igst", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("rounding_adjustment", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("engine_version", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_invoices_org_id_organizations"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_invoices_project_id_projects"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], name="fk_invoices_quote_id_quotes"),
        sa.ForeignKeyConstraint(["credit_note_of_id"], ["invoices.id"],
                                name="fk_invoices_credit_note_of_id_invoices"),
        sa.PrimaryKeyConstraint("id", name="pk_invoices"),
        sa.UniqueConstraint("org_id", "number", name="uq_invoices_org_id"),
        sa.CheckConstraint("taxable + cgst + sgst + igst + rounding_adjustment = total",
                           name="ck_invoices_invoice_reconciles"),
    )
    op.create_index("ix_invoices_org_id", "invoices", ["org_id"])

    op.create_table(
        "invoice_lines",
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("hsn", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), server_default="1", nullable=False),
        sa.Column("taxable_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_invoice_lines_org_id_organizations"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name="fk_invoice_lines_invoice_id_invoices"),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_lines"),
    )
    op.create_index("ix_invoice_lines_org_id", "invoice_lines", ["org_id"])

    op.execute(_IMMUTABLE_FN)
    op.execute(
        "CREATE TRIGGER invoices_immutable BEFORE UPDATE ON invoices "
        "FOR EACH ROW EXECUTE FUNCTION forbid_issued_invoice_update();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS invoices_immutable ON invoices;")
    op.execute("DROP FUNCTION IF EXISTS forbid_issued_invoice_update();")
    op.drop_index("ix_invoice_lines_org_id", "invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_org_id", "invoices")
    op.drop_table("invoices")
    op.drop_index("ix_document_counters_org_id", "document_counters")
    op.drop_table("document_counters")
