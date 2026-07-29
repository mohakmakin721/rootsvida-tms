"""Provenance + staging models (Part 2 §4.6, plan §13, §30).

`SourceDocument` = one immutable input artifact (a workbook file, a vendor email,
a rate-card PDF, a WhatsApp image), fingerprinted by SHA-256 so a changed source
is detectable and re-ingestion is idempotent.

`RawImportRow` = one row of a source, preserved VERBATIM as JSONB before any
normalisation. This is the staging layer that sits between messy Excel and the
canonical tables (plan §30): nothing is parsed away, and every canonical record
can be traced back to the exact cell-set it came from.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ParserStrategy, RawParseStatus, SourceKind
from app.models.types import pg_enum


class SourceDocument(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "source_documents"
    # A given file (by content hash) is one source document per org; re-ingesting
    # the same bytes resolves to the same row instead of duplicating.
    __table_args__ = (UniqueConstraint("org_id", "sha256"),)

    kind: Mapped[SourceKind] = mapped_column(
        pg_enum(SourceKind, "source_kind"), nullable=False
    )
    # sender address / sheet source / phone / original path.
    origin: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(Text)
    object_key: Mapped[str | None] = mapped_column(Text)  # S3/MinIO key
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    raw_rows: Mapped[list[RawImportRow]] = relationship(
        back_populates="source_document"
    )


class RawImportRow(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "raw_import_rows"
    # One staging row per source cell-set. This is the idempotency key: a re-run
    # over the same file/sheet/row upserts rather than duplicating (plan §29).
    __table_args__ = (
        UniqueConstraint(
            "source_document_id", "sheet_name", "row_number",
            name="uq_raw_import_rows_source_document_id",
        ),
    )

    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id"), nullable=False
    )
    sheet_name: Mapped[str | None] = mapped_column(Text)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # The full row, verbatim, as {column_name: raw_value}. Never destroyed.
    raw_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Stable hash of the raw content — lets a re-run detect an unchanged row.
    row_hash: Mapped[str | None] = mapped_column(Text)
    parser_strategy: Mapped[ParserStrategy | None] = mapped_column(
        pg_enum(ParserStrategy, "parser_strategy")
    )
    parse_status: Mapped[RawParseStatus] = mapped_column(
        pg_enum(RawParseStatus, "raw_parse_status"),
        nullable=False,
        default=RawParseStatus.PENDING,
        server_default=RawParseStatus.PENDING.value,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    source_document: Mapped[SourceDocument] = relationship(back_populates="raw_rows")
