"""GST invoices — the immutable tax document (Phase 4).

An invoice is generated from an **issued quote** and freezes everything: a gapless
number, the seller's and buyer's identity, the HSN/place-of-supply, and the tax
breakdown (taxable + CGST/SGST/IGST + rounding, reconciling to the total). It is
immutable by DB trigger — a correction is a **credit note** (`kind='credit_note'`,
`credit_note_of_id` pointing at the cancelled original), never an edit.

Gapless numbering (a GST requirement) is served by `DocumentCounter`: one row per
(org, kind, financial year), incremented under a row lock so numbers never skip —
unlike a raw sequence, which would gap on rollback.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import GstTreatment
from app.models.types import pg_enum


class DocumentCounter(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    """A gapless per-(org, kind, FY) counter. Incremented under SELECT … FOR UPDATE."""

    __tablename__ = "document_counters"
    __table_args__ = (UniqueConstraint("org_id", "kind", "fiscal_year"),)

    kind: Mapped[str] = mapped_column(Text, nullable=False)  # 'invoice'
    fiscal_year: Mapped[str] = mapped_column(Text, nullable=False)  # '2026-27'
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class Invoice(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("org_id", "number"),
        # The GST identity: the parts must reconcile to the total (mirrors the
        # engine's TaxBreakdown invariant).
        CheckConstraint(
            "taxable + cgst + sgst + igst + rounding_adjustment = total",
            name="invoice_reconciles",
        ),
    )

    number: Mapped[str] = mapped_column(Text, nullable=False)  # 'RV/2026-27/0001'
    fiscal_year: Mapped[str] = mapped_column(Text, nullable=False)
    serial: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="invoice"
    )  # invoice | credit_note
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="issued"
    )  # issued | cancelled
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotes.id"), nullable=False)
    project_code: Mapped[str | None] = mapped_column(Text)  # the 'Ref' on the document
    # A credit note references the invoice it corrects.
    credit_note_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"))

    # Frozen seller identity.
    seller_name: Mapped[str] = mapped_column(Text, nullable=False)
    seller_gstin: Mapped[str | None] = mapped_column(Text)
    seller_pan: Mapped[str | None] = mapped_column(Text)
    seller_state_code: Mapped[str | None] = mapped_column(Text)
    seller_state_name: Mapped[str | None] = mapped_column(Text)
    seller_address: Mapped[str | None] = mapped_column(Text)

    # Frozen buyer identity.
    buyer_name: Mapped[str] = mapped_column(Text, nullable=False)
    buyer_country: Mapped[str | None] = mapped_column(Text)
    buyer_gstin: Mapped[str | None] = mapped_column(Text)
    place_of_supply: Mapped[str | None] = mapped_column(Text)

    # Frozen tax (the GST identity). All INR — the authoritative money (D-0001).
    hsn: Mapped[str | None] = mapped_column(Text)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)  # 0.0500
    gst_treatment: Mapped[GstTreatment] = mapped_column(
        pg_enum(GstTreatment, "gst_treatment"), nullable=False
    )
    taxable: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    sgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    igst: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    rounding_adjustment: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    notes: Mapped[str | None] = mapped_column(Text)
    engine_version: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list[InvoiceLine]] = relationship(back_populates="invoice")


class InvoiceLine(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    hsn: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default="1")
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
