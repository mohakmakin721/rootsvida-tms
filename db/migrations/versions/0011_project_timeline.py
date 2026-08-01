"""project timeline: status_changed_at, travel window, milestones

Revision ID: 0011_project_timeline
Revises: 0010_quote_currency
Create Date: 2026-08-01

Makes timeline tracking first-class (Phase 3 M10): adds `status_changed_at`,
`travel_start`, `travel_end` to `projects`, and a `project_milestones` table for
dated deadlines (payments, invoice due dates, custom). Status stays a text column;
the `ProjectStatus` enum validates it in the API.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_project_timeline"
down_revision: str | None = "0010_quote_currency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("travel_start", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("travel_end", sa.Date(), nullable=True))

    op.create_table(
        "project_milestones",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), server_default="deadline", nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("done", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_project_milestones_org_id_organizations"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"],
                                name="fk_project_milestones_project_id_projects"),
        sa.PrimaryKeyConstraint("id", name="pk_project_milestones"),
    )
    op.create_index("ix_project_milestones_org_id", "project_milestones", ["org_id"])
    op.create_index("ix_project_milestones_project_id", "project_milestones", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_milestones_project_id", "project_milestones")
    op.drop_index("ix_project_milestones_org_id", "project_milestones")
    op.drop_table("project_milestones")
    op.drop_column("projects", "travel_end")
    op.drop_column("projects", "travel_start")
    op.drop_column("projects", "status_changed_at")
