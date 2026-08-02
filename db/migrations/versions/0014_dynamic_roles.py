"""dynamic roles & permissions (D-0015)

Revision ID: 0014_dynamic_roles
Revises: 0013_drop_saarc_pax_class
Create Date: 2026-08-02

Roles become data instead of a fixed enum: a `roles` table (org-scoped, permissions
as a text[]) plus a conversion of `users.role` from the `user_role` PG enum to plain
text (a role's `key`). Every existing org is seeded with the five built-in roles and
their default permissions, reproducing the previous hardcoded gates exactly, so all
current users keep the access they had.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.services.roles import ensure_system_roles

revision: str = "0014_dynamic_roles"
down_revision: str | None = "0013_drop_saarc_pax_class"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                  nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False),
        sa.Column("permissions", postgresql.ARRAY(sa.Text()),
                  server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_roles_org_id_organizations"),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("org_id", "key", name="uq_roles_org_id"),
    )
    op.create_index("ix_roles_org_id", "roles", ["org_id"])

    # users.role: user_role enum -> plain text (a role key).
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE text USING role::text")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'readonly'")
    op.execute("DROP TYPE user_role")

    # Seed the built-in roles for every existing org (idempotent).
    session = Session(bind=op.get_bind())
    for (org_id,) in session.execute(sa.text("SELECT id FROM organizations")):
        ensure_system_roles(session, org_id)
    session.flush()


def downgrade() -> None:
    op.execute(
        "CREATE TYPE user_role AS ENUM "
        "('owner', 'ops_manager', 'sales', 'accounts', 'readonly')"
    )
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'readonly'")
    op.drop_index("ix_roles_org_id", table_name="roles")
    op.drop_table("roles")
