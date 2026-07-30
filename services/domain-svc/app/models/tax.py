"""GST tax rules — the place-of-supply rule set, documented as data.

One row per `PlaceOfSupply` scenario (intra-state / inter-state / international),
recording the treatment and the split rates that apply. The pure pricing engine
consumes whichever row the resolver selects, so the *policy* lives in the DB and
can change without a code deploy (Part 2 §1.4). The seller is Uttarakhand (05).

**Not tax advice.** These rows encode the rule set the operator chose; the
export/international treatment in particular should be confirmed with a CA
(D-0013). Every scenario is overridable per booking with a logged reason.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import GstTreatment, PlaceOfSupply
from app.models.types import pg_enum


class TaxRule(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "tax_rules"
    # One default rule per scenario per org.
    __table_args__ = (UniqueConstraint("org_id", "scenario"),)

    scenario: Mapped[PlaceOfSupply] = mapped_column(
        pg_enum(PlaceOfSupply, "place_of_supply"), nullable=False
    )
    treatment: Mapped[GstTreatment] = mapped_column(
        pg_enum(GstTreatment, "gst_treatment"), nullable=False
    )
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)  # 0.0500
    cgst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    sgst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    igst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    hsn: Mapped[str | None] = mapped_column(Text)  # '998555'
    rounding_policy: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="gross_nearest_100"
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
