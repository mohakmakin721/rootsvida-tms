"""Itinerary domain: projects, itineraries, segments, days, presence, components.

The structural heart of Phase 3 (Part 2 §4.2–4.3). The load-bearing table is
`day_segment_presence`: which traveller segments are present on which day. That
is what turns "Indians leave on day 4, foreigners stay to day 6" into a data fact
the pricing engine reads — replacing the workbook's hardcoded SUM ranges.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AllocationBasis, ComponentKind, Occupancy, PaxClass
from app.models.types import pg_enum


class Project(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    """One enquiry = one project (code 'TP10'), holding its itineraries + quotes.

    Timeline tracking is first-class (M10): the project carries its lifecycle status
    with the moment it last changed, the travel window, and a set of dated
    milestones (payments, invoice due dates, custom deadlines) — not just a status
    string.
    """

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("org_id", "code"),)

    code: Mapped[str] = mapped_column(Text, nullable=False)
    # `client_id` links to the canonical client record (M8); `client_name` stays as
    # a denormalised snapshot so legacy rows and quick drafts still read cleanly.
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))
    client_name: Mapped[str] = mapped_column(Text, nullable=False)
    client_country: Mapped[str | None] = mapped_column(Text)  # ISO-2, e.g. 'CL'
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="enquiry"
    )  # enquiry|quoted|confirmed|operating|closed|lost
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    travel_start: Mapped[date | None] = mapped_column(Date)
    travel_end: Mapped[date | None] = mapped_column(Date)

    itineraries: Mapped[list[Itinerary]] = relationship(back_populates="project")
    milestones: Mapped[list[ProjectMilestone]] = relationship(back_populates="project")


class ProjectMilestone(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    """A dated deadline on a project's timeline — a payment, an invoice due date, or
    any custom milestone. `amount` carries the sum for payment milestones."""

    __tablename__ = "project_milestones"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    kind: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="note"
    )  # payment|payment_deadline|invoice|note
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    done: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="milestones")


class Itinerary(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "itineraries"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    destination: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str | None] = mapped_column(Text)  # travellers' start point
    # Planning notes / constraints — extra include/exclude points the owner adds;
    # fed to the AI drafter and kept with the itinerary.
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    generated_by: Mapped[str | None] = mapped_column(Text)  # 'human' | 'agent:...'

    project: Mapped[Project] = relationship(back_populates="itineraries")
    segments: Mapped[list[TravellerSegment]] = relationship(back_populates="itinerary")
    days: Mapped[list[ItineraryDay]] = relationship(back_populates="itinerary")


class TravellerSegment(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    """Foreign Single / Foreign Double / Indian Double — a pax_class × occupancy
    × count, with the markup rule that applies to it."""

    __tablename__ = "traveller_segments"
    __table_args__ = (CheckConstraint("pax_count > 0", name="ck_traveller_segments_pax_count"),)

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itineraries.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    pax_class: Mapped[PaxClass] = mapped_column(pg_enum(PaxClass, "pax_class"), nullable=False)
    occupancy: Mapped[Occupancy] = mapped_column(pg_enum(Occupancy, "occupancy"), nullable=False)
    pax_count: Mapped[int] = mapped_column(Integer, nullable=False)
    markup_rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("markup_rules.id"))

    itinerary: Mapped[Itinerary] = relationship(back_populates="segments")


class ItineraryDay(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "itinerary_days"
    __table_args__ = (UniqueConstraint("itinerary_id", "day_number"),)

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itineraries.id"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    destination_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("destinations.id"))
    narrative: Mapped[str | None] = mapped_column(Text)  # LLM-written, human-edited

    itinerary: Mapped[Itinerary] = relationship(back_populates="days")
    components: Mapped[list[ItineraryComponent]] = relationship(back_populates="day")


class DaySegmentPresence(OrgScopedMixin, Base):
    """THE key table: (day, segment) — who is present on which day."""

    __tablename__ = "day_segment_presence"

    itinerary_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itinerary_days.id"), primary_key=True
    )
    traveller_segment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("traveller_segments.id"), primary_key=True
    )


class ItineraryComponent(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    """A costed line on a day: a stay, transport, guide, activity, etc. Links to a
    canonical rate (or carries a manual override, which requires a reason)."""

    __tablename__ = "itinerary_components"
    __table_args__ = (
        CheckConstraint(
            "override_amount IS NULL OR override_reason IS NOT NULL",
            name="ck_itinerary_components_override_reason",
        ),
    )

    itinerary_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itinerary_days.id"), nullable=False
    )
    kind: Mapped[ComponentKind] = mapped_column(
        pg_enum(ComponentKind, "component_kind"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    rate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rates.id"))
    transport_rate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transport_rates.id"))
    activity_rate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("activity_rates.id"))
    guide_rate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("guide_rates.id"))
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="1")
    override_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    override_reason: Mapped[str | None] = mapped_column(Text)
    allocation: Mapped[AllocationBasis] = mapped_column(
        pg_enum(AllocationBasis, "allocation_basis"),
        nullable=False,
        server_default=AllocationBasis.ALL_PAX.value,
    )
    applies_to_segment_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True))
    )
    applies_to_pax_class: Mapped[PaxClass | None] = mapped_column(pg_enum(PaxClass, "pax_class"))
    description: Mapped[str | None] = mapped_column(Text)

    day: Mapped[ItineraryDay] = relationship(back_populates="components")
