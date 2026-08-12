"""Structured shapes the LLM layer produces (Phase 5, 5a-M3).

Deliberately close to the itinerary tables (itineraries → days → components) so a
draft maps cleanly into the builder in M4. Per the amended pricing model, a component
MAY carry an `estimate_amount` (flagged, unverified) — the deterministic engine still
owns every total; there is no total/price rollup field here by design.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class IntakeParse(BaseModel):
    """Structured fields parsed from a pasted client-form response (flexible intake).

    Every field is optional: the parser fills what it can find, the owner reviews.
    """

    destination: str | None = None
    origin: str | None = None
    group_size: int | None = None
    themes: list[str] = Field(default_factory=list)
    duration_days: int | None = None
    tier: str | None = None
    budget_inr: Decimal | None = None
    nationality: str | None = None
    age_band: str | None = None
    transport: list[str] = Field(default_factory=list)
    notes: str | None = None
    raw: str = ""


class DraftCandidate(BaseModel):
    """A ranked candidate handed to the drafter (from the rule engine)."""

    id: str
    name: str
    kind: str = "stay"
    score: float = 0.0


class DraftComponent(BaseModel):
    kind: str  # ComponentKind value: stay|transport|activity|guide|meal|permit|misc
    title: str
    supplier_id: str | None = None
    supplier_name: str | None = None
    allocation: str = "all_pax"
    notes: str = ""
    # Optional unverified estimate (source = llm_estimate); NOT a final price.
    estimate_amount: Decimal | None = None
    estimate_currency: str = "INR"


class DraftDay(BaseModel):
    day_number: int
    title: str
    place: str
    narrative: str
    components: list[DraftComponent] = Field(default_factory=list)


class ItineraryDraft(BaseModel):
    title: str
    theme: str
    region: str
    duration_days: int
    duration_nights: int
    overview: str
    days: list[DraftDay] = Field(default_factory=list)
    inclusions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    ops_notes: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class DraftBrief(BaseModel):
    """Everything the drafter needs: the full trip brief + rule-engine-ranked
    candidates. The richer this is, the more closely the draft fits the client."""

    destination: str = ""
    origin: str = ""  # travellers' start point — drives transport / transfers
    duration_days: int = 3
    group_size: int | None = None
    themes: list[str] = Field(default_factory=list)
    tier: str | None = None
    budget_inr: Decimal | None = None
    age_band: str | None = None
    transport: list[str] = Field(default_factory=list)
    # Traveller mix, from the builder's traveller groups. `has_foreign` matters for
    # pricing (foreign vs Indian monument tickets / guide fees differ); `pax_summary`
    # + `occupancy_summary` guide accommodation choice.
    has_foreign: bool = False
    pax_summary: str = ""
    occupancy_summary: str = ""
    # Free-text planning notes / constraints the owner wants respected.
    notes: str = ""
    candidates: list[DraftCandidate] = Field(default_factory=list)
