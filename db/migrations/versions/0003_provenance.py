"""provenance and staging: source_documents + raw_import_rows

Revision ID: 0003_provenance
Revises: 7e604edc5cfc
Create Date: 2026-07-29

Adds the provenance/staging layer (Part 2 §4.6, plan §13/§30):
  - source_documents: one fingerprinted input artifact (unique per org+sha256)
  - raw_import_rows: verbatim staged rows (JSONB), the idempotency key for reingest
  - FK from every rate table's source_document_id -> source_documents

Hand-written (autogenerate kept hanging on a sluggish local DB): the three new
ENUM types are created once up front (create_type=False) and dropped on downgrade.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models import enums as e

revision: str = "0003_provenance"
down_revision: str | None = "7e604edc5cfc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(enum_cls: type, name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*[m.value for m in enum_cls], name=name, create_type=False)


source_kind = _enum(e.SourceKind, "source_kind")
parser_strategy = _enum(e.ParserStrategy, "parser_strategy")
raw_parse_status = _enum(e.RawParseStatus, "raw_parse_status")
NEW_ENUMS = [source_kind, parser_strategy, raw_parse_status]

# Rate tables that gain an FK on their existing source_document_id column.
_RATE_TABLES = ["rates", "transport_rates", "activity_rates", "guide_rates", "misc_costs"]


def upgrade() -> None:
    bind = op.get_bind()
    for en in NEW_ENUMS:
        en.create(bind, checkfirst=True)

    op.create_table(
        "source_documents",
        sa.Column("kind", source_kind, nullable=False),
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                  nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_source_documents_org_id_organizations"),
        sa.PrimaryKeyConstraint("id", name="pk_source_documents"),
        sa.UniqueConstraint("org_id", "sha256",
                            name="uq_source_documents_org_id"),
    )
    op.create_index("ix_source_documents_org_id", "source_documents", ["org_id"])

    op.create_table(
        "raw_import_rows",
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        sa.Column("sheet_name", sa.Text(), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_values", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False),
        sa.Column("row_hash", sa.Text(), nullable=True),
        sa.Column("parser_strategy", parser_strategy, nullable=True),
        sa.Column("parse_status", raw_parse_status,
                  server_default="pending", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                  nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_raw_import_rows_org_id_organizations"),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_documents.id"],
            name="fk_raw_import_rows_source_document_id_source_documents"),
        sa.PrimaryKeyConstraint("id", name="pk_raw_import_rows"),
        sa.UniqueConstraint("source_document_id", "sheet_name", "row_number",
                            name="uq_raw_import_rows_source_document_id"),
    )
    op.create_index("ix_raw_import_rows_org_id", "raw_import_rows", ["org_id"])

    for tbl in _RATE_TABLES:
        op.create_foreign_key(
            f"fk_{tbl}_source_document_id_source_documents",
            tbl, "source_documents", ["source_document_id"], ["id"],
        )


def downgrade() -> None:
    for tbl in _RATE_TABLES:
        op.drop_constraint(
            f"fk_{tbl}_source_document_id_source_documents", tbl, type_="foreignkey"
        )
    op.drop_table("raw_import_rows")
    op.drop_table("source_documents")

    bind = op.get_bind()
    for en in NEW_ENUMS:
        en.drop(bind, checkfirst=True)
