"""Resolve the org and the source document a staging run writes under.

A source document is keyed on `(org_id, sha256)`: ingesting the same bytes twice
returns the same row (idempotent, plan §29). Everything staged in a run hangs off
the document returned here, so provenance is established before any row is read.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import get_settings
from app.models import Organization, SourceDocument
from app.models.enums import SourceKind
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.hashing import sha256_file


def resolve_org_id(session: Session, slug: str | None = None) -> uuid.UUID:
    """Return the id of the seeded organization (by slug; defaults to config).

    Raises `LookupError` rather than inventing an org — staging must run under a
    real tenant, and a missing one means `scripts/seed_org.py` was not run.
    """
    slug = slug or get_settings().rv_org_slug
    org_id = session.scalar(select(Organization.id).where(Organization.slug == slug))
    if org_id is None:
        raise LookupError(
            f"organization {slug!r} not found — run `python scripts/seed_org.py` first"
        )
    return org_id


def get_or_create_source_document(
    session: Session,
    org_id: uuid.UUID,
    path: str | Path,
    *,
    kind: SourceKind = SourceKind.LEGACY_XLSX,
    origin: str | None = None,
) -> tuple[SourceDocument, bool]:
    """Fetch the source document for this file's bytes, or create it.

    Returns `(document, created)`. Idempotent on `(org_id, sha256)`.
    """
    path = Path(path)
    sha = sha256_file(path)
    existing = session.scalar(
        select(SourceDocument).where(
            SourceDocument.org_id == org_id, SourceDocument.sha256 == sha
        )
    )
    if existing is not None:
        return existing, False

    doc = SourceDocument(
        org_id=org_id,
        kind=kind,
        filename=path.name,
        origin=origin or path.name,
        sha256=sha,
    )
    session.add(doc)
    session.flush()
    return doc, True
