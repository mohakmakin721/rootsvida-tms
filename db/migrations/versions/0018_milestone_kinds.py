"""remap project_milestone kinds to payment / payment_deadline / invoice / note

Revision ID: 0018_milestone_kinds
Revises: 0017_client_corporate_name
Create Date: 2026-08-03

Milestone vocabulary (owner spec): `payment` = money received on the date;
`payment_deadline` = a pending/expected payment; `invoice` = auto-tracked when an
invoice is raised; `note` = a manual dated update. Old 'deadline' → 'payment_deadline',
old 'other' → 'note'. `kind` is plain text (no enum), so this is a data update.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018_milestone_kinds"
down_revision: str | None = "0017_client_corporate_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE project_milestones SET kind = 'payment_deadline' WHERE kind = 'deadline'")
    op.execute("UPDATE project_milestones SET kind = 'note' WHERE kind = 'other'")
    op.alter_column("project_milestones", "kind", server_default="note")


def downgrade() -> None:
    op.execute("UPDATE project_milestones SET kind = 'deadline' WHERE kind = 'payment_deadline'")
    op.alter_column("project_milestones", "kind", server_default="deadline")
