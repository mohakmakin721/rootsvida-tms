"""clients: first-class buyer records + projects.client_id

Revision ID: 0009_clients
Revises: 0008_user_password
Create Date: 2026-08-01

Adds the `clients` table (Phase 3 M8) and its `client_type` ENUM, plus a nullable
`client_id` FK on `projects`. Existing projects keep their `client_name` snapshot
and simply carry a NULL `client_id` until linked. Same hand-written ENUM pattern
as 0005.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models import enums as e

revision: str = "0009_clients"
down_revision: str | None = "0008_user_password"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

client_type = postgresql.ENUM(
    *[m.value for m in e.ClientType], name="client_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    client_type.create(bind, checkfirst=True)

    op.create_table(
        "clients",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("client_type", client_type, server_default="individual", nullable=False),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("referral", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                  nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_clients_org_id_organizations"),
        sa.PrimaryKeyConstraint("id", name="pk_clients"),
    )
    op.create_index("ix_clients_org_id", "clients", ["org_id"])

    op.add_column("projects", sa.Column("client_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_projects_client_id_clients", "projects", "clients", ["client_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_client_id_clients", "projects", type_="foreignkey")
    op.drop_column("projects", "client_id")
    op.drop_index("ix_clients_org_id", "clients")
    op.drop_table("clients")
    client_type.drop(op.get_bind(), checkfirst=True)
