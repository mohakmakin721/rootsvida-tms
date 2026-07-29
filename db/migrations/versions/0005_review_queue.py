"""review queue: the human gate between candidates and canonical

Revision ID: 0005_review_queue
Revises: 0004_raw_row_link
Create Date: 2026-07-30

Adds `review_queue` (Part 2 §4.6) plus its two ENUM types (`review_status`,
`review_entity_type`), created once up front (create_type=False) and dropped on
downgrade — same hand-written pattern as 0003.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models import enums as e

revision: str = "0005_review_queue"
down_revision: str | None = "0004_raw_row_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(enum_cls: type, name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*[m.value for m in enum_cls], name=name, create_type=False)


review_status = _enum(e.ReviewStatus, "review_status")
review_entity_type = _enum(e.ReviewEntityType, "review_entity_type")
NEW_ENUMS = [review_status, review_entity_type]


def upgrade() -> None:
    bind = op.get_bind()
    for en in NEW_ENUMS:
        en.create(bind, checkfirst=True)

    op.create_table(
        "review_queue",
        sa.Column("entity_type", review_entity_type, nullable=False),
        sa.Column("proposed", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("existing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("status", review_status, server_default="pending", nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                  nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_review_queue_org_id_organizations"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"],
                                name="fk_review_queue_source_document_id_source_documents"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"],
                                name="fk_review_queue_reviewed_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_review_queue"),
        sa.UniqueConstraint("org_id", "dedupe_key", name="uq_review_queue_org_id"),
    )
    op.create_index("ix_review_queue_org_id", "review_queue", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_review_queue_org_id", "review_queue")
    op.drop_table("review_queue")
    bind = op.get_bind()
    for en in NEW_ENUMS:
        en.drop(bind, checkfirst=True)
