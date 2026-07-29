"""Deduplication: find likely-duplicate suppliers and queue them for review.

Plan §1.3: fuzzy-match on normalise(name) within a destination, present the pairs
as merge candidates, and **never auto-merge**. This module only *detects* and
*enqueues* `merge_candidate` review items; a human approves, and only then is the
merge executed (`app.services.merge`). Detection is a pure function over
(id, name, destination) tuples so it is testable without a database.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.models import Supplier
from app.models.enums import ReviewEntityType
from app.services import review
from sqlalchemy import select
from sqlalchemy.orm import Session

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace — the comparison key."""
    return _NON_ALNUM.sub(" ", name.lower()).strip()


@dataclass(frozen=True)
class SupplierRec:
    id: uuid.UUID
    name: str
    destination_id: uuid.UUID | None


@dataclass(frozen=True)
class DupPair:
    left_id: uuid.UUID
    right_id: uuid.UUID
    score: float


def find_duplicate_pairs(
    records: list[SupplierRec], threshold: float = 0.84
) -> list[DupPair]:
    """Return supplier pairs whose normalised names are similar (>= threshold),
    compared only within the same destination. Highest score first."""
    by_dest: dict[uuid.UUID | None, list[SupplierRec]] = {}
    for rec in records:
        by_dest.setdefault(rec.destination_id, []).append(rec)

    pairs: list[DupPair] = []
    for group in by_dest.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                na, nb = normalize_name(a.name), normalize_name(b.name)
                if not na or not nb:
                    continue
                score = 1.0 if na == nb else SequenceMatcher(None, na, nb).ratio()
                if score >= threshold:
                    lo, hi = sorted((a.id, b.id), key=str)
                    pairs.append(DupPair(lo, hi, round(score, 3)))
    return sorted(pairs, key=lambda p: p.score, reverse=True)


def _snapshot(s: Supplier) -> dict[str, str | None]:
    return {
        "id": str(s.id),
        "display_name": s.display_name,
        "kind": s.kind.value,
        "category": s.category,
        "property_type": s.property_type,
        "destination_id": str(s.destination_id) if s.destination_id else None,
    }


def enqueue_merge_candidates(
    session: Session, org_id: uuid.UUID, threshold: float = 0.84
) -> int:
    """Detect duplicate supplier pairs and enqueue each as a merge_candidate
    review item. Idempotent per pair (dedupe_key). Returns the number created."""
    suppliers = list(
        session.scalars(
            select(Supplier).where(
                Supplier.org_id == org_id, Supplier.deleted_at.is_(None)
            )
        ).all()
    )
    by_id = {s.id: s for s in suppliers}
    records = [SupplierRec(s.id, s.display_name, s.destination_id) for s in suppliers]

    created = 0
    for pair in find_duplicate_pairs(records, threshold):
        a, b = by_id[pair.left_id], by_id[pair.right_id]
        # Deterministic primary: the older row survives (created_at, then id).
        primary, duplicate = sorted((a, b), key=lambda s: (s.created_at, str(s.id)))
        key = f"merge:{min(str(a.id), str(b.id))}:{max(str(a.id), str(b.id))}"
        before = review.get_by_dedupe_key(session, org_id, key)
        review.enqueue(
            session,
            org_id,
            entity_type=ReviewEntityType.MERGE_CANDIDATE,
            proposed={
                "primary": _snapshot(primary),
                "duplicate": _snapshot(duplicate),
                "score": pair.score,
                "reason": "fuzzy name match within destination",
            },
            existing=_snapshot(primary),
            confidence=pair.score,
            dedupe_key=key,
        )
        if before is None:
            created += 1
    return created
