"""SQLAlchemy models package.

Milestone 1 defines only the declarative `Base` (with a naming convention so
Alembic emits stable, predictable constraint names). Canonical tables are added
in Milestone 3; importing them here registers them on `Base.metadata` for
Alembic autogenerate.
"""

from __future__ import annotations

from app.models.base import Base
from app.models.org import Organization, User

# Importing model modules here registers their tables on Base.metadata for
# Alembic autogenerate. Milestone 3+ adds supplier/rate/provenance modules.

__all__ = ["Base", "Organization", "User"]
