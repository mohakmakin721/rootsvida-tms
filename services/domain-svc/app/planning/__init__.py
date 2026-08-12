"""Planning — the pure, deterministic rule engine behind the Phase-5 drafter.

No I/O, no DB, no LLM: it turns a client intake into per-client priority weights
and ranks candidate places / hotels / experiences by a weighted score under hard
constraints. Kept pure (like the `pricing` engine) so it is instant and fully
unit-testable, which is what powers the builder's live recalibration.
"""

from __future__ import annotations

from app.planning.rule_engine import (
    BASE_WEIGHTS,
    Candidate,
    IntakeSignals,
    Priority,
    ScoredCandidate,
    derive_weights,
    rank,
    score,
    theme_mix,
)

__all__ = [
    "BASE_WEIGHTS",
    "Candidate",
    "IntakeSignals",
    "Priority",
    "ScoredCandidate",
    "derive_weights",
    "rank",
    "score",
    "theme_mix",
]
