"""Planning service (Phase 5, 5a-M4) — the glue between intake, rule engine, DB and LLM.

Flow: intake → per-client weights (rule engine) → candidate suppliers from our DB,
scored per priority → ranked → an ItineraryDraft from the active LLM provider (stub
unless Gemini is configured). No prices are computed here — the deterministic engine
prices the draft once it's in the builder.

`score_supplier` is a pure heuristic (v1). It is deliberately simple; richer scoring
(proximity, seasonality, embeddings) arrives with the geospatial/RAG milestones.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import (
    DraftBrief,
    DraftCandidate,
    ItineraryDraft,
    enforce_day_categories,
    get_provider,
)
from app.models import Destination, Supplier
from app.models.enums import SupplierKind
from app.planning import (
    Candidate,
    IntakeSignals,
    Priority,
    ScoredCandidate,
    derive_weights,
    rank,
)

# Kinds we pull as candidates for a draft (stays + the main experience kinds).
_DEFAULT_KINDS = (
    SupplierKind.STAY, SupplierKind.ACTIVITY, SupplierKind.GUIDE, SupplierKind.MEAL,
)

class SuggestResult(BaseModel):
    weights: dict[str, float]
    candidates: list[DraftCandidate]
    draft: ItineraryDraft
    # What the deterministic per-day category check flagged/auto-added after the LLM
    # returned (missing stays/meals/transport/permits, main legs, soft gaps).
    warnings: list[str] = []


def score_supplier(
    kind: str,
    category: str | None,
    property_type: str | None,
    tags: Sequence[str],
    themes: Sequence[str],
) -> dict[Priority, float]:
    """Per-priority scores (0–100) for a supplier — pure v1 heuristic."""
    cat = (category or "").lower()
    ptype = (property_type or "").lower()
    tagset = {t.lower() for t in tags}
    themeset = {t.lower() for t in themes}

    if "luxury" in cat or "super" in cat:
        comfort = 90.0
    elif "mid" in cat:
        comfort = 65.0
    elif "budget" in cat:
        comfort = 40.0
    else:
        comfort = 55.0

    authenticity = 55.0
    if any(k in ptype for k in ("heritage", "camp", "boutique")):
        authenticity = 85.0
    if "homestay" in ptype or "homestay" in tagset:
        authenticity = 90.0

    haystack = " ".join([cat, ptype, *tagset])
    hits = sum(
        1 for theme in themeset if any(word and word in haystack for word in theme.split())
    )
    if not themeset:
        experience = 55.0
    elif hits:
        experience = min(50.0 + hits * 20.0, 95.0)
    else:
        experience = 45.0

    return {
        Priority.EXPERIENCE_MATCH: experience,
        Priority.COMFORT: comfort,
        Priority.AUTHENTICITY: authenticity,
        # proximity/seasonality/pace/budget_fit/logistics stay neutral in v1.
    }


def _to_candidate(supplier: Supplier, themes: Sequence[str]) -> Candidate:
    return Candidate(
        id=str(supplier.id),
        name=supplier.display_name,
        scores=score_supplier(
            supplier.kind.value, supplier.category, supplier.property_type,
            supplier.tags, themes,
        ),
    )


def assemble_candidates(
    session: Session,
    org_id: uuid.UUID,
    *,
    destination: str | None,
    kinds: Sequence[SupplierKind] = _DEFAULT_KINDS,
    themes: Sequence[str] = (),
    limit: int = 40,
) -> list[Candidate]:
    """Pull candidate suppliers from the DB, scored per priority.

    Prefers suppliers in the requested destination; falls back to all matching kinds
    if the destination has no matches yet (so the drafter always has something to work
    with)."""
    stmt = (
        select(Supplier, Destination.name)
        .join(Destination, Supplier.destination_id == Destination.id, isouter=True)
        .where(Supplier.org_id == org_id, Supplier.deleted_at.is_(None))
    )
    if kinds:
        stmt = stmt.where(Supplier.kind.in_(list(kinds)))
    pairs: list[tuple[Supplier, str | None]] = [
        (row[0], row[1]) for row in session.execute(stmt.limit(500))
    ]

    if destination:
        needle = destination.strip().lower()
        matched: list[tuple[Supplier, str | None]] = [
            (s, n) for (s, n) in pairs if n and needle in n.lower()
        ]
        pairs = matched or pairs

    return [_to_candidate(s, themes) for (s, _n) in pairs[:limit]]


def _summarize_segments(
    segments: Sequence[dict[str, object]],
) -> tuple[int | None, bool, str, str]:
    """(group_size, has_foreign, pax_summary, occupancy_summary) from traveller groups."""
    if not segments:
        return None, False, "", ""
    total = sum(int(str(s.get("pax_count") or 0)) for s in segments)
    has_foreign = any(str(s.get("pax_class")).lower() == "foreign" for s in segments)
    by_class: dict[str, int] = {}
    by_occ: dict[str, int] = {}
    for s in segments:
        pc = str(s.get("pax_class") or "?")
        oc = str(s.get("occupancy") or "?")
        n = int(str(s.get("pax_count") or 0))
        by_class[pc] = by_class.get(pc, 0) + n
        by_occ[oc] = by_occ.get(oc, 0) + n
    pax_summary = f"{total} travellers: " + ", ".join(f"{n} {k}" for k, n in by_class.items())
    occupancy_summary = ", ".join(f"{n} {k}" for k, n in by_occ.items())
    return total, has_foreign, pax_summary, occupancy_summary


def _prepare(
    session: Session,
    org_id: uuid.UUID,
    *,
    destination: str | None,
    origin: str | None,
    duration_days: int | None,
    group_size: int | None,
    themes: Sequence[str],
    tier: str | None,
    budget_inr: Decimal | None,
    age_band: str | None,
    transport: Sequence[str],
    segments: Sequence[dict[str, object]],
    notes: str | None,
) -> tuple[dict[str, float], list[DraftCandidate], DraftBrief]:
    """Shared front half of suggest/refine: intake → weights + ranked DB candidates +
    the full DraftBrief the model reasons over."""
    seg_size, has_foreign, pax_summary, occupancy_summary = _summarize_segments(segments)
    group_size = seg_size or group_size
    signals = IntakeSignals(
        themes=list(themes), tier=tier, budget_inr=budget_inr,
        group_size=group_size, duration_days=duration_days,
        age_band=age_band, transport=list(transport),
    )
    weights = derive_weights(signals)
    candidates = assemble_candidates(
        session, org_id, destination=destination, themes=themes
    )
    ranked: list[ScoredCandidate] = rank(candidates, weights)

    # Look up each ranked candidate's kind for the brief (kept off the pure engine).
    kind_by_id = {
        str(sid): kind.value
        for sid, kind in session.execute(
            select(Supplier.id, Supplier.kind).where(Supplier.org_id == org_id)
        )
    }
    draft_candidates = [
        DraftCandidate(
            id=sc.candidate.id, name=sc.candidate.name,
            kind=kind_by_id.get(sc.candidate.id, "stay"), score=sc.score,
        )
        for sc in ranked
    ]

    brief = DraftBrief(
        destination=destination or "",
        origin=origin or "",
        duration_days=duration_days or 3,
        group_size=group_size,
        themes=list(themes),
        tier=tier,
        budget_inr=budget_inr,
        age_band=age_band,
        transport=list(transport),
        has_foreign=has_foreign,
        pax_summary=pax_summary,
        occupancy_summary=occupancy_summary,
        notes=notes or "",
        candidates=draft_candidates,
    )
    weights_dict = {p.value: w for p, w in weights.items()}
    return weights_dict, draft_candidates, brief


def suggest(
    session: Session,
    org_id: uuid.UUID,
    *,
    destination: str | None = None,
    origin: str | None = None,
    duration_days: int | None = None,
    group_size: int | None = None,
    themes: Sequence[str] = (),
    tier: str | None = None,
    budget_inr: Decimal | None = None,
    age_band: str | None = None,
    transport: Sequence[str] = (),
    segments: Sequence[dict[str, object]] = (),
    notes: str | None = None,
) -> SuggestResult:
    """Intake → weights → ranked DB candidates → LLM draft. The heart of the panel.

    Traveller groups (pax class / occupancy / counts) refine the true group size, the
    weights, and the brief the model reasons over (foreign vs Indian ticket/guide
    rates; accommodation suited to the occupancy mix)."""
    weights, candidates, brief = _prepare(
        session, org_id, destination=destination, origin=origin,
        duration_days=duration_days, group_size=group_size, themes=themes, tier=tier,
        budget_inr=budget_inr, age_band=age_band, transport=transport,
        segments=segments, notes=notes,
    )
    # Always the real LLM draft (with its estimates). If the provider is transiently
    # overloaded, _generate's retries ride it out; a persistent failure surfaces as a
    # readable "AI busy — try again" message (via the API layer) rather than a
    # priceless fallback draft that hides the estimates.
    draft = get_provider().draft(brief)
    # Deterministic net: guarantee every day has its required categories (stay/meal/
    # transport, main legs, known permits) regardless of what the LLM returned.
    draft, warnings = enforce_day_categories(draft, brief)
    return SuggestResult(
        weights=weights, candidates=candidates, draft=draft, warnings=warnings
    )


def refine(
    session: Session,
    org_id: uuid.UUID,
    *,
    draft: ItineraryDraft,
    instruction: str,
    destination: str | None = None,
    origin: str | None = None,
    duration_days: int | None = None,
    group_size: int | None = None,
    themes: Sequence[str] = (),
    tier: str | None = None,
    budget_inr: Decimal | None = None,
    age_band: str | None = None,
    transport: Sequence[str] = (),
    segments: Sequence[dict[str, object]] = (),
    notes: str | None = None,
) -> SuggestResult:
    """Apply a free-text change request to an existing draft (the follow-up chat).

    Rebuilds the same brief as suggest (so budget/pax/candidates still apply), asks the
    provider to edit the draft, then runs the same deterministic category/budget net."""
    weights, candidates, brief = _prepare(
        session, org_id, destination=destination, origin=origin,
        duration_days=duration_days, group_size=group_size, themes=themes, tier=tier,
        budget_inr=budget_inr, age_band=age_band, transport=transport,
        segments=segments, notes=notes,
    )
    updated = get_provider().refine(brief, draft, instruction)
    updated, warnings = enforce_day_categories(updated, brief)
    return SuggestResult(
        weights=weights, candidates=candidates, draft=updated, warnings=warnings
    )
