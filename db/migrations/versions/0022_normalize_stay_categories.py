"""Owner batch: normalize stay-vendor `category` into the canonical tier set

Revision ID: 0022_normalize_stay_categories
Revises: 0021_itinerary_dest_origin_notes
Create Date: 2026-08-14

Existing stay vendors carry free-text categories (Budget, Mid, Mid-Range, MId range,
Lux, Luxury, Super Lux, …). This one-time data migration folds them into the owner's
canonical vocabulary — Homestays, Hostels, 2/3/4/5/7 Star — matching the stay-vendor
Category field + AI "Accommodation" list.

Rules (case/spacing-insensitive; idempotent — re-running is a no-op):
  • property_type wins first:  homestay → Homestays ·  hostel → Hostels
  • otherwise map the old category string:
        budget, budget to mid range      → 2 Star
        bud lux                          → 3 Star
        mid, mid range                   → 3 Star
        mid lux                          → 4 Star
        lux, luxury                      → 5 Star
        super lux, super luxury          → 7 Star
  • anything unrecognized (or blank)     → left untouched for manual review

Only `kind = 'stay'` rows are touched. Non-stay vendors keep their categories.
Irreversible in intent (the original free-text is lost), so downgrade() is a no-op.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_normalize_stay_categories"
down_revision: str | None = "0021_itinerary_dest_origin_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Normalized old category → canonical tier.
_CATEGORY_MAP: dict[str, str] = {
    "budget": "2 Star",
    "budget to mid range": "2 Star",
    "bud lux": "3 Star",
    "mid": "3 Star",
    "mid range": "3 Star",
    "mid lux": "4 Star",
    "lux": "5 Star",
    "luxury": "5 Star",
    "super lux": "7 Star",
    "super luxury": "7 Star",
}


def _norm(value: str | None) -> str:
    """Lowercase, trim, and collapse hyphens/underscores/runs of space to one space."""
    if not value:
        return ""
    return re.sub(r"[\s\-_]+", " ", value.strip().lower()).strip()


def _canonical(category: str | None, property_type: str | None) -> str | None:
    ptype = _norm(property_type)
    if "homestay" in ptype:
        return "Homestays"
    if "hostel" in ptype:
        return "Hostels"
    return _CATEGORY_MAP.get(_norm(category))


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, category, property_type FROM suppliers WHERE kind = 'stay'")
    ).fetchall()
    update = sa.text("UPDATE suppliers SET category = :cat WHERE id = :id")
    for sid, category, property_type in rows:
        new = _canonical(category, property_type)
        if new is not None and new != category:
            bind.execute(update, {"cat": new, "id": sid})


def downgrade() -> None:
    # One-way data normalization — the original free-text categories are not retained.
    pass
