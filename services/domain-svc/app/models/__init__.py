"""SQLAlchemy models package.

Milestone 1 defines only the declarative `Base` (with a naming convention so
Alembic emits stable, predictable constraint names). Canonical tables are added
in Milestone 3; importing them here registers them on `Base.metadata` for
Alembic autogenerate.
"""

from __future__ import annotations

from app.models.base import Base

# Milestone 3+ will import model modules here so they register on the metadata,
# e.g.:  from app.models import supplier, rate, provenance  # noqa

__all__ = ["Base"]
