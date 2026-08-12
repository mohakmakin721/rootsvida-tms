"""Phase 5 M1: itinerary intakes + rate price_status/rate_source

Revision ID: 0019_intake_and_rate_pricing
Revises: 0018_milestone_kinds
Create Date: 2026-08-11

Adds the Phase-5 pricing-confidence surface (amends D-0001): every rate-bearing
table gains `price_status` (estimate | on_file | confirmed) and `rate_source`
(internal | internet | b2b | b2c | llm_estimate) via the shared ProvenanceMixin.
Existing rows default to on_file / internal (they are our own data). Also creates
`itinerary_intakes` — the structured client brief the rule engine + drafter work
from. Same hand-written ENUM pattern as 0009.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models import enums as e

revision: str = "0019_intake_and_rate_pricing"
down_revision: str | None = "0018_milestone_kinds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

price_status = postgresql.ENUM(
    *[m.value for m in e.PriceStatus], name="price_status", create_type=False
)
rate_source = postgresql.ENUM(
    *[m.value for m in e.RateSource], name="rate_source", create_type=False
)
pax_class = postgresql.ENUM(
    *[m.value for m in e.PaxClass], name="pax_class", create_type=False
)

# Every table carrying ProvenanceMixin gets the two new pricing columns.
_RATE_TABLES = ["rates", "transport_rates", "activity_rates", "guide_rates", "misc_costs"]


def upgrade() -> None:
    bind = op.get_bind()
    price_status.create(bind, checkfirst=True)
    rate_source.create(bind, checkfirst=True)

    for tbl in _RATE_TABLES:
        op.add_column(
            tbl,
            sa.Column("price_status", price_status,
                      server_default="on_file", nullable=False),
        )
        op.add_column(
            tbl,
            sa.Column("rate_source", rate_source,
                      server_default="internal", nullable=False),
        )

    op.create_table(
        "itinerary_intakes",
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("destination", sa.Text(), nullable=True),
        sa.Column("group_size", sa.Integer(), nullable=True),
        sa.Column("themes", postgresql.ARRAY(sa.Text()),
                  server_default="{}", nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("travel_start", sa.Date(), nullable=True),
        sa.Column("travel_end", sa.Date(), nullable=True),
        sa.Column("tier", sa.Text(), nullable=True),
        sa.Column("budget_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column("pax_class", pax_class, nullable=True),
        sa.Column("nationality", sa.Text(), nullable=True),
        sa.Column("age_band", sa.Text(), nullable=True),
        sa.Column("transport", postgresql.ARRAY(sa.Text()),
                  server_default="{}", nullable=False),
        sa.Column("service_types", postgresql.ARRAY(sa.Text()),
                  server_default="{}", nullable=False),
        sa.Column("must_include", sa.Text(), nullable=True),
        sa.Column("must_exclude", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("priority_weights", postgresql.JSONB(), nullable=True),
        sa.Column("raw", postgresql.JSONB(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                  nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name="fk_itinerary_intakes_org_id_organizations"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"],
                                name="fk_itinerary_intakes_project_id_projects"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"],
                                name="fk_itinerary_intakes_client_id_clients"),
        sa.PrimaryKeyConstraint("id", name="pk_itinerary_intakes"),
    )
    op.create_index("ix_itinerary_intakes_org_id", "itinerary_intakes", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_itinerary_intakes_org_id", "itinerary_intakes")
    op.drop_table("itinerary_intakes")
    for tbl in _RATE_TABLES:
        op.drop_column(tbl, "rate_source")
        op.drop_column(tbl, "price_status")
    bind = op.get_bind()
    rate_source.drop(bind, checkfirst=True)
    price_status.drop(bind, checkfirst=True)
