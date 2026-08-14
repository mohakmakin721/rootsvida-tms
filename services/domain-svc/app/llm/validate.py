"""Deterministic per-day category guarantee (Phase 5, 5a-M8).

The LLM prompt (see `gemini.py`) *asks* the model to walk the seven categories for
every day, but a prompt is only guidance — a one-shot flash model can still leave a
night with no stay, a day with no meal, or forget a border permit. This module is the
hard net: pure Python, no LLM, no I/O. It runs after the model returns and:

  1. detects per-day category gaps against fixed invariants, and
  2. repairs them by inserting **no-price placeholder** components the human reviewer
     must complete (estimate_amount stays None — D-0001: code never invents a number).

Invariants enforced (repaired):
  • STAY  — every night (days 1..D-1; the final day is departure, no new stay).
  • MEAL  — every day.
  • TRANSPORT (local) — every day.
  • MAIN LEG — an outbound origin→destination leg on day 1 and a return on the last
    day, when an `origin` distinct from the destination is known.
  • PERMIT — when a day's place matches a known permit-required location.

Soft checks (warned, never mutated): a missing Visa on an international trip, and a
day with no activity (the "wholistic feel"). Everything the validator changes is also
reported in the returned warnings so the owner sees exactly what was auto-added.
"""

from __future__ import annotations

from decimal import Decimal

from app.llm.schema import DraftBrief, DraftComponent, DraftDay, ItineraryDraft

# Known places whose entry is gated by a non-negotiable permit. Matched (case-
# insensitively) against each day's place/title/narrative. Value = permit label.
# Deliberately small and high-precision; extend as the ops team hits new ones.
PERMIT_PLACES: dict[str, str] = {
    "wagah": "Attari-Wagah border permit / ceremony pass",
    "attari": "Attari-Wagah border permit / ceremony pass",
    "harshil": "Inner-line permit (Harshil / Nelong valley)",
    "nelong": "Inner-line permit (Nelong valley)",
    "gangotri": "Gangotri National Park entry permit",
    "nathu la": "Nathu La protected-area permit",
    "nathula": "Nathu La protected-area permit",
    "nubra": "Inner-line permit (Nubra valley)",
    "pangong": "Inner-line permit (Pangong Tso)",
    "tso moriri": "Inner-line permit (Tso Moriri)",
    "nelang": "Inner-line permit (Nelong valley)",
}


def _kinds(day: DraftDay) -> set[str]:
    return {(c.kind or "").strip().lower() for c in day.components}


def _blob(day: DraftDay) -> str:
    parts = [day.place, day.title, day.narrative, *(c.title for c in day.components)]
    return " ".join(p for p in parts if p).lower()


def _placeholder(kind: str, title: str, note: str) -> DraftComponent:
    return DraftComponent(
        kind=kind,
        title=title,
        allocation="all_pax",
        notes=f"Auto-added by the category check — {note}",
        estimate_amount=None,
    )


def _has_main_leg(day: DraftDay, origin: str, destination: str) -> bool:
    """Heuristic: does this day already carry the long-haul origin<->destination leg?"""
    o, d = origin.strip().lower(), destination.strip().lower()
    for c in day.components:
        if (c.kind or "").lower() != "transport":
            continue
        text = f"{c.title} {c.notes}".lower()
        if (o and o in text) or (d and d in text):
            return True
        if any(
            w in text
            for w in ("flight", "train", "rail", "outbound", "return", "arrival", "departure")
        ):
            return True
    return False


def enforce_day_categories(
    draft: ItineraryDraft, brief: DraftBrief
) -> tuple[ItineraryDraft, list[str]]:
    """Repair per-day category gaps in place and return (draft, warnings).

    Pure and idempotent: running it twice adds nothing the second time (placeholders
    satisfy the same invariants). Never touches estimate_amount / prices."""
    warnings: list[str] = []
    days = sorted(draft.days, key=lambda d: d.day_number)
    if not days:
        return draft, ["Draft has no days — nothing to validate."]

    last_num = days[-1].day_number
    origin = (brief.origin or "").strip()
    destination = (brief.destination or draft.region or "").strip()
    international = bool(brief.has_foreign)

    for day in days:
        kinds = _kinds(day)
        is_departure_day = day.day_number == last_num and len(days) > 1

        # STAY — every night except the departure day.
        if not is_departure_day and "stay" not in kinds:
            day.components.append(
                _placeholder(
                    "stay",
                    "Overnight stay (needs review)",
                    "pick a property and confirm the rate.",
                )
            )
            warnings.append(
                f"Day {day.day_number}: added a placeholder STAY (no accommodation was drafted)."
            )

        # MEAL — every day.
        if "meal" not in kinds:
            day.components.append(
                _placeholder(
                    "meal",
                    "Meals for the day (needs review)",
                    "set the meal plan (B/L/D) and rate.",
                )
            )
            warnings.append(
                f"Day {day.day_number}: added a placeholder MEAL (guest eats every day)."
            )

        # TRANSPORT (local) — every day.
        if "transport" not in kinds:
            day.components.append(
                _placeholder(
                    "transport",
                    "Local transport (needs review)",
                    "assign a cab/coach and confirm the fare.",
                )
            )
            warnings.append(f"Day {day.day_number}: added a placeholder local TRANSPORT.")

        # PERMIT — non-negotiable where the place is known to require one.
        blob = _blob(day)
        for needle, label in PERMIT_PLACES.items():
            if needle in blob and "permit" not in kinds:
                day.components.append(
                    _placeholder(
                        "permit",
                        label,
                        "REQUIRED permit — arrange in advance and price it.",
                    )
                )
                warnings.append(f"Day {day.day_number}: added a required PERMIT ({label}).")
                break

    # MAIN LEG — outbound on day 1, return on the last day, when origin is known.
    if origin and destination and origin.lower() != destination.lower():
        first, last = days[0], days[-1]
        if not _has_main_leg(first, origin, destination):
            first.components.append(
                _placeholder(
                    "transport",
                    f"Outbound {origin} → {destination} (flight/train/car — needs review)",
                    "choose the mode and confirm the fare.",
                )
            )
            warnings.append(
                f"Day {first.day_number}: added the outbound {origin}→{destination} main leg."
            )
        if len(days) > 1 and not _has_main_leg(last, origin, destination):
            last.components.append(
                _placeholder(
                    "transport",
                    f"Return {destination} → {origin} (flight/train/car — needs review)",
                    "choose the mode and confirm the fare.",
                )
            )
            warnings.append(
                f"Day {last.day_number}: added the return {destination}→{origin} main leg."
            )

    # Soft warnings — surfaced, not mutated.
    if international:
        all_titles = " ".join(c.title.lower() for d in days for c in d.components if c.title)
        if "visa" not in all_titles:
            warnings.append(
                "International trip: no Visa component found — add one if travellers need a visa."
            )
    for day in days:
        if "activity" not in _kinds(day):
            warnings.append(
                f"Day {day.day_number}: no ACTIVITY — consider adding the "
                "signature experience for a fuller feel."
            )

    _budget_warning(draft, brief, warnings)
    return draft, warnings


# Allocations whose estimate_amount is a PER-PERSON figure (multiplied by head-count);
# everything else is treated as a shared whole-group amount.
_PER_PAX_ALLOCATIONS = {"per_pax_direct", "by_pax_class"}


def _budget_warning(draft: ItineraryDraft, brief: DraftBrief, warnings: list[str]) -> None:
    """Rough grand-total from the LLM's estimates vs the group's budget. Estimates are
    unverified (the engine owns real pricing), so this only flags a likely overshoot —
    it never blocks. Per-person items are multiplied by the traveller count; shared
    items counted once."""
    budget = brief.budget_inr
    if budget is None or budget <= 0:
        return
    pax = brief.group_size or 1
    total = Decimal(0)
    for day in draft.days:
        for c in day.components:
            if c.estimate_amount is None:
                continue
            per_pax = (c.allocation or "").strip().lower() in _PER_PAX_ALLOCATIONS
            total += c.estimate_amount * (pax if per_pax else 1)
    if total > budget:
        over = total - budget
        warnings.append(
            f"Estimated total ~₹{total:,.0f} exceeds the budget ₹{budget:,.0f} by "
            f"~₹{over:,.0f} (rough, from unverified estimates) — trim options or flag "
            "the client before quoting."
        )
