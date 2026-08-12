"""The weighted-priority rule engine (Phase 5, 5a-M2).

Deliberately simple and deterministic — a weighted-score model, not ML:

1. `derive_weights(intake)` turns the client's brief into a per-client weight
   vector over the eight priorities (normalised to sum 100). This is the "dynamic
   weights per client" requirement: the same engine yields a wellness-led plan for
   one client and a luxury-offsite plan for another, purely from the weights.
2. `score(candidate, weights)` is the weighted average of a candidate's per-priority
   scores (0–100) → a single 0–100 number.
3. `rank(candidates, weights, max_cost=...)` applies hard constraints then sorts.

The mapping from a real hotel/place into per-priority `scores` (feature extraction)
is a later concern (RAG / geospatial milestones); this module is the scoring core.
Weights are owner-overridable downstream — `derive_weights` only sets the default.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class Priority(StrEnum):
    """The eight scoring dimensions (owner-approved)."""

    EXPERIENCE_MATCH = "experience_match"
    COMFORT = "comfort"
    BUDGET_FIT = "budget_fit"
    PACE = "pace"
    PROXIMITY = "proximity"
    SEASONALITY = "seasonality"
    AUTHENTICITY = "authenticity"
    LOGISTICS = "logistics"


# RootsVida default weights (sum = 100). The starting point before the client's
# brief nudges them. Authenticity always carries some weight (brand DNA).
BASE_WEIGHTS: dict[Priority, float] = {
    Priority.EXPERIENCE_MATCH: 30.0,
    Priority.AUTHENTICITY: 15.0,
    Priority.BUDGET_FIT: 15.0,
    Priority.COMFORT: 10.0,
    Priority.PROXIMITY: 10.0,
    Priority.PACE: 8.0,
    Priority.SEASONALITY: 7.0,
    Priority.LOGISTICS: 5.0,
}

# No priority ever drops to zero — every dimension keeps a floor so a plan is never
# blind to it. Applied before re-normalising to 100.
MIN_WEIGHT = 1.0

# Budget bands, INR per person per day. Below LOW → budget dominates; above HIGH →
# comfort/experience get room to breathe.
LOW_PPPD = Decimal("5000")
HIGH_PPPD = Decimal("20000")

# Neutral score for a priority a candidate says nothing about.
NEUTRAL_SCORE = 50.0


@dataclass(frozen=True)
class IntakeSignals:
    """The subset of the client intake the weighting reads. The service layer maps
    an `ItineraryIntake` row onto this; the engine stays free of the DB."""

    themes: Sequence[str] = ()
    tier: str | None = None
    budget_inr: Decimal | None = None
    group_size: int | None = None
    duration_days: int | None = None
    age_band: str | None = None
    transport: Sequence[str] = ()


@dataclass(frozen=True)
class Candidate:
    """A place / hotel / experience to be ranked. `scores` are 0–100 per priority;
    any priority omitted is treated as neutral. `cost` (per relevant unit) drives the
    optional hard budget filter."""

    id: str
    name: str
    scores: Mapping[Priority, float] = field(default_factory=dict)
    cost: Decimal | None = None


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: float


def _normalize(weights: Mapping[Priority, float]) -> dict[Priority, float]:
    """Floor each weight then scale so the vector sums to exactly 100."""
    floored = {p: max(float(w), MIN_WEIGHT) for p, w in weights.items()}
    total = sum(floored.values())
    return {p: round(w / total * 100, 2) for p, w in floored.items()}


def _per_pax_per_day(sig: IntakeSignals) -> Decimal | None:
    if sig.budget_inr is None or not sig.group_size or not sig.duration_days:
        return None
    denom = sig.group_size * sig.duration_days
    if denom <= 0:
        return None
    return sig.budget_inr / Decimal(denom)


def derive_weights(sig: IntakeSignals) -> dict[Priority, float]:
    """Per-client priority weights from the intake, normalised to sum 100.

    Deterministic nudges on top of BASE_WEIGHTS; the result is a sensible default
    the owner can still override with sliders.
    """
    w = dict(BASE_WEIGHTS)

    tier = (sig.tier or "").strip().lower()
    if "luxury" in tier:
        w[Priority.COMFORT] += 10
        w[Priority.BUDGET_FIT] -= 8
    elif tier and ("hostel" in tier or "homestay" in tier or "budget" in tier):
        w[Priority.BUDGET_FIT] += 6
        w[Priority.AUTHENTICITY] += 4
        w[Priority.COMFORT] -= 6

    pppd = _per_pax_per_day(sig)
    if pppd is not None:
        if pppd < LOW_PPPD:
            w[Priority.BUDGET_FIT] += 10
        elif pppd > HIGH_PPPD:
            w[Priority.BUDGET_FIT] -= 6
            w[Priority.COMFORT] += 4
            w[Priority.EXPERIENCE_MATCH] += 2

    age = (sig.age_band or "").strip().lower()
    if "above" in age or "40+" in age or "41" in age:
        w[Priority.PACE] += 8
        w[Priority.EXPERIENCE_MATCH] -= 2
    elif age.startswith("18"):
        w[Priority.PACE] -= 4
        w[Priority.EXPERIENCE_MATCH] += 2

    modes = {t.strip().lower() for t in sig.transport}
    ground_only = bool(modes) and not any(m.startswith("flight") for m in modes)
    if ground_only:
        w[Priority.PROXIMITY] += 8
    elif any(m.startswith("flight") for m in modes):
        w[Priority.PROXIMITY] -= 2

    if len(sig.themes) >= 3:
        w[Priority.EXPERIENCE_MATCH] += 6

    return _normalize(w)


def theme_mix(
    themes: Sequence[str], importance: Mapping[str, float] | None = None
) -> dict[str, float]:
    """Split the experience-match weight across the selected themes (sums to 100).

    Equal split by default; pass `importance` (owner-tunable) to weight some themes
    more than others. Empty selection → empty mix.
    """
    if not themes:
        return {}
    imp = {t: float(importance.get(t, 1.0)) if importance else 1.0 for t in themes}
    total = sum(imp.values()) or 1.0
    return {t: round(v / total * 100, 2) for t, v in imp.items()}


def score(candidate: Candidate, weights: Mapping[Priority, float]) -> float:
    """Weighted average of the candidate's per-priority scores → 0–100.

    Missing priorities count as neutral (50) so a sparse candidate isn't unfairly
    punished. Assumes `weights` sums to 100 (as `derive_weights` guarantees)."""
    total_w = sum(weights.values()) or 1.0
    acc = 0.0
    for priority, weight in weights.items():
        s = float(candidate.scores.get(priority, NEUTRAL_SCORE))
        acc += weight * s
    return round(acc / total_w, 2)


def rank(
    candidates: Sequence[Candidate],
    weights: Mapping[Priority, float],
    *,
    max_cost: Decimal | None = None,
) -> list[ScoredCandidate]:
    """Filter by the hard budget constraint, score, and sort best-first.

    Sort is stable on the input order for ties, so results are deterministic.
    """
    eligible = [
        c for c in candidates
        if max_cost is None or c.cost is None or c.cost <= max_cost
    ]
    scored = [ScoredCandidate(candidate=c, score=score(c, weights)) for c in eligible]
    scored.sort(key=lambda sc: sc.score, reverse=True)
    return scored
