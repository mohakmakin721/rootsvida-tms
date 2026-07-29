"""SQLAlchemy models package.

Milestone 1 defines only the declarative `Base` (with a naming convention so
Alembic emits stable, predictable constraint names). Canonical tables are added
in Milestone 3; importing them here registers them on `Base.metadata` for
Alembic autogenerate.
"""

from __future__ import annotations

from app.models.activity import ActivityRate, GuideRate
from app.models.base import Base
from app.models.destination import Destination
from app.models.misc import MiscCost
from app.models.org import Organization, User
from app.models.provenance import RawImportRow, SourceDocument
from app.models.rate import Rate
from app.models.review import ReviewItem
from app.models.supplier import (
    RoomType,
    Supplier,
    SupplierCommercials,
    SupplierContact,
)
from app.models.transport import TransportRate

# Importing model modules here registers their tables on Base.metadata for
# Alembic autogenerate. Milestone 4 adds source_documents / review_queue.

__all__ = [
    "ActivityRate",
    "Base",
    "Destination",
    "GuideRate",
    "MiscCost",
    "Organization",
    "RawImportRow",
    "Rate",
    "ReviewItem",
    "RoomType",
    "SourceDocument",
    "Supplier",
    "SupplierCommercials",
    "SupplierContact",
    "TransportRate",
    "User",
]
