"""itineraries & quotes: projects → quote_lines + markup_rules (+ immutability)

Revision ID: 0007_itineraries_quotes
Revises: 0006_tax_rules
Create Date: 2026-07-30

Phase 3 data model (Part 2 §4.2–4.4): projects, itineraries, traveller_segments,
itinerary_days, day_segment_presence, itinerary_components, quotes, quote_lines,
plus markup_rules. New enums component_kind + markup_basis. Quotes carry a DB
trigger that makes an issued quote immutable (only → 'superseded').
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models import enums as e

revision: str = "0007_itineraries_quotes"
down_revision: str | None = "0006_tax_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(enum_cls: type, name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*[m.value for m in enum_cls], name=name, create_type=False)


# New enums (created here) + existing ones (referenced only).
component_kind = _enum(e.ComponentKind, "component_kind")
markup_basis = _enum(e.MarkupBasis, "markup_basis")
NEW_ENUMS = [component_kind, markup_basis]

pax_class = _enum(e.PaxClass, "pax_class")
occupancy = _enum(e.Occupancy, "occupancy")
allocation_basis = _enum(e.AllocationBasis, "allocation_basis")
gst_treatment = _enum(e.GstTreatment, "gst_treatment")


def _org_cols() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    ]


def _org_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                   name=f"fk_{table}_org_id_organizations")


_IMMUTABLE_FN = """
CREATE OR REPLACE FUNCTION forbid_issued_quote_update() RETURNS trigger AS $$
BEGIN
  IF OLD.status <> 'draft' AND NEW.status <> 'superseded' THEN
    RAISE EXCEPTION 'Quote % is issued and immutable. Create a new version.', OLD.id;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    bind = op.get_bind()
    for en in NEW_ENUMS:
        en.create(bind, checkfirst=True)

    op.create_table(
        "markup_rules",
        *_org_cols(),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("basis", markup_basis, server_default="markup_on_cost", nullable=False),
        sa.Column("rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        _org_fk("markup_rules"),
        sa.PrimaryKeyConstraint("id", name="pk_markup_rules"),
        sa.UniqueConstraint("org_id", "label", name="uq_markup_rules_org_id"),
    )
    op.create_index("ix_markup_rules_org_id", "markup_rules", ["org_id"])

    op.create_table(
        "projects",
        *_org_cols(),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=False),
        sa.Column("client_country", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default="enquiry", nullable=False),
        _org_fk("projects"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"],
                                name="fk_projects_owner_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("org_id", "code", name="uq_projects_org_id"),
    )
    op.create_index("ix_projects_org_id", "projects", ["org_id"])

    op.create_table(
        "itineraries",
        *_org_cols(),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("generated_by", sa.Text(), nullable=True),
        _org_fk("itineraries"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"],
                                name="fk_itineraries_project_id_projects"),
        sa.PrimaryKeyConstraint("id", name="pk_itineraries"),
    )
    op.create_index("ix_itineraries_org_id", "itineraries", ["org_id"])

    op.create_table(
        "traveller_segments",
        *_org_cols(),
        sa.Column("itinerary_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("pax_class", pax_class, nullable=False),
        sa.Column("occupancy", occupancy, nullable=False),
        sa.Column("pax_count", sa.Integer(), nullable=False),
        sa.Column("markup_rule_id", sa.UUID(), nullable=True),
        _org_fk("traveller_segments"),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"],
                                name="fk_traveller_segments_itinerary_id_itineraries"),
        sa.ForeignKeyConstraint(["markup_rule_id"], ["markup_rules.id"],
                                name="fk_traveller_segments_markup_rule_id_markup_rules"),
        sa.PrimaryKeyConstraint("id", name="pk_traveller_segments"),
        sa.CheckConstraint("pax_count > 0", name="ck_traveller_segments_pax_count"),
    )
    op.create_index("ix_traveller_segments_org_id", "traveller_segments", ["org_id"])

    op.create_table(
        "itinerary_days",
        *_org_cols(),
        sa.Column("itinerary_id", sa.UUID(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("destination_id", sa.UUID(), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=True),
        _org_fk("itinerary_days"),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"],
                                name="fk_itinerary_days_itinerary_id_itineraries"),
        sa.ForeignKeyConstraint(["destination_id"], ["destinations.id"],
                                name="fk_itinerary_days_destination_id_destinations"),
        sa.PrimaryKeyConstraint("id", name="pk_itinerary_days"),
        sa.UniqueConstraint("itinerary_id", "day_number", name="uq_itinerary_days_itinerary_id"),
    )
    op.create_index("ix_itinerary_days_org_id", "itinerary_days", ["org_id"])

    op.create_table(
        "day_segment_presence",
        sa.Column("itinerary_day_id", sa.UUID(), nullable=False),
        sa.Column("traveller_segment_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        _org_fk("day_segment_presence"),
        sa.ForeignKeyConstraint(["itinerary_day_id"], ["itinerary_days.id"],
                                name="fk_day_segment_presence_itinerary_day_id_itinerary_days"),
        sa.ForeignKeyConstraint(
            ["traveller_segment_id"], ["traveller_segments.id"],
            name="fk_day_segment_presence_traveller_segment_id_traveller_segments"),
        sa.PrimaryKeyConstraint("itinerary_day_id", "traveller_segment_id",
                                name="pk_day_segment_presence"),
    )
    op.create_index("ix_day_segment_presence_org_id", "day_segment_presence", ["org_id"])

    op.create_table(
        "itinerary_components",
        *_org_cols(),
        sa.Column("itinerary_day_id", sa.UUID(), nullable=False),
        sa.Column("kind", component_kind, nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=True),
        sa.Column("rate_id", sa.UUID(), nullable=True),
        sa.Column("transport_rate_id", sa.UUID(), nullable=True),
        sa.Column("activity_rate_id", sa.UUID(), nullable=True),
        sa.Column("guide_rate_id", sa.UUID(), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), server_default="1", nullable=False),
        sa.Column("override_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("allocation", allocation_basis, server_default="all_pax", nullable=False),
        sa.Column("applies_to_segment_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.Column("applies_to_pax_class", pax_class, nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        _org_fk("itinerary_components"),
        sa.ForeignKeyConstraint(["itinerary_day_id"], ["itinerary_days.id"],
                                name="fk_itinerary_components_itinerary_day_id_itinerary_days"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"],
                                name="fk_itinerary_components_supplier_id_suppliers"),
        sa.ForeignKeyConstraint(["rate_id"], ["rates.id"],
                                name="fk_itinerary_components_rate_id_rates"),
        sa.ForeignKeyConstraint(["transport_rate_id"], ["transport_rates.id"],
                                name="fk_itinerary_components_transport_rate_id_transport_rates"),
        sa.ForeignKeyConstraint(["activity_rate_id"], ["activity_rates.id"],
                                name="fk_itinerary_components_activity_rate_id_activity_rates"),
        sa.ForeignKeyConstraint(["guide_rate_id"], ["guide_rates.id"],
                                name="fk_itinerary_components_guide_rate_id_guide_rates"),
        sa.PrimaryKeyConstraint("id", name="pk_itinerary_components"),
        sa.CheckConstraint("override_amount IS NULL OR override_reason IS NOT NULL",
                           name="ck_itinerary_components_override_reason"),
    )
    op.create_index("ix_itinerary_components_org_id", "itinerary_components", ["org_id"])

    op.create_table(
        "quotes",
        *_org_cols(),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("itinerary_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("gst_treatment", gst_treatment, nullable=False),
        sa.Column("fx_rate_inr_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("fx_rate_locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rounding_policy", sa.Text(), nullable=False),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_taxable", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_tax", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_gross", sa.Numeric(14, 2), nullable=True),
        sa.Column("margin_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("pricing_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("engine_version", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.UUID(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        _org_fk("quotes"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"],
                                name="fk_quotes_project_id_projects"),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"],
                                name="fk_quotes_itinerary_id_itineraries"),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"],
                                name="fk_quotes_issued_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_quotes"),
        sa.UniqueConstraint("project_id", "version", name="uq_quotes_project_id"),
    )
    op.create_index("ix_quotes_org_id", "quotes", ["org_id"])

    op.create_table(
        "quote_lines",
        *_org_cols(),
        sa.Column("quote_id", sa.UUID(), nullable=False),
        sa.Column("traveller_segment_id", sa.UUID(), nullable=True),
        sa.Column("component_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cost_per_pax", sa.Numeric(14, 2), nullable=True),
        sa.Column("sell_per_pax", sa.Numeric(14, 2), nullable=True),
        sa.Column("pax_count", sa.Integer(), nullable=True),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=True),
        _org_fk("quote_lines"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], name="fk_quote_lines_quote_id_quotes"),
        sa.ForeignKeyConstraint(["traveller_segment_id"], ["traveller_segments.id"],
                                name="fk_quote_lines_traveller_segment_id_traveller_segments"),
        sa.ForeignKeyConstraint(["component_id"], ["itinerary_components.id"],
                                name="fk_quote_lines_component_id_itinerary_components"),
        sa.PrimaryKeyConstraint("id", name="pk_quote_lines"),
    )
    op.create_index("ix_quote_lines_org_id", "quote_lines", ["org_id"])

    # Immutability by trigger, not convention (Part 2 §4.4).
    op.execute(_IMMUTABLE_FN)
    op.execute(
        "CREATE TRIGGER quotes_immutable BEFORE UPDATE ON quotes "
        "FOR EACH ROW EXECUTE FUNCTION forbid_issued_quote_update();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS quotes_immutable ON quotes;")
    op.execute("DROP FUNCTION IF EXISTS forbid_issued_quote_update();")
    for table in (
        "quote_lines", "quotes", "itinerary_components", "day_segment_presence",
        "itinerary_days", "traveller_segments", "itineraries", "projects", "markup_rules",
    ):
        op.drop_table(table)
    bind = op.get_bind()
    for en in NEW_ENUMS:
        en.drop(bind, checkfirst=True)
