"""Deterministic stub LLM provider (Phase 5, 5a-M3).

No network, no spend, no randomness: it turns a brief + ranked candidates into a
structurally valid `ItineraryDraft` so the whole pipeline and the M4 builder UI work
and are testable before a live key exists. It writes plain scaffold prose (not the
RootsVida voice — that's the real model's job) and **invents no prices** (every
`estimate_amount` stays None; pricing comes from the deterministic engine).
"""

from __future__ import annotations

from app.llm.base import LLMProvider
from app.llm.schema import (
    DraftBrief,
    DraftComponent,
    DraftDay,
    IntakeParse,
    ItineraryDraft,
)

# Sensible default allocation basis per component kind.
_ALLOCATION = {
    "stay": "per_segment",
    "transport": "all_pax",
    "guide": "all_pax",
    "activity": "per_pax_direct",
    "meal": "all_pax",
    "permit": "per_pax_direct",
    "misc": "all_pax",
}


class StubProvider(LLMProvider):
    name = "stub"

    def parse_intake(self, text: str) -> IntakeParse:
        # A stub can't understand free text; it just preserves the raw paste for the
        # owner to fill in. The live provider does the real extraction.
        return IntakeParse(raw=text)

    def draft(self, brief: DraftBrief) -> ItineraryDraft:
        days_n = max(brief.duration_days, 1)
        nights = max(days_n - 1, 0)
        place = brief.destination or "your destination"
        theme_bits = ", ".join(brief.themes[:3]) if brief.themes else "a tailored mix"

        stays = [c for c in brief.candidates if c.kind == "stay"]
        experiences = [c for c in brief.candidates if c.kind != "stay"]

        days: list[DraftDay] = []
        for i in range(days_n):
            components: list[DraftComponent] = []
            if stays:
                s = stays[i % len(stays)]
                components.append(
                    DraftComponent(
                        kind="stay", title=s.name, supplier_id=s.id,
                        supplier_name=s.name, allocation=_ALLOCATION["stay"],
                        notes="Top-ranked stay — confirm rate for these dates.",
                    )
                )
            if experiences:
                e = experiences[i % len(experiences)]
                components.append(
                    DraftComponent(
                        kind=e.kind, title=e.name, supplier_id=e.id,
                        supplier_name=e.name,
                        allocation=_ALLOCATION.get(e.kind, "all_pax"),
                        notes="Ranked candidate.",
                    )
                )
            days.append(
                DraftDay(
                    day_number=i + 1,
                    title=f"Day {i + 1} in {place}",
                    place=place,
                    narrative=(
                        f"Day {i + 1}: explore {place} with a focus on {theme_bits}. "
                        "(Scaffold draft — the live model will write this in the "
                        "RootsVida voice.)"
                    ),
                    components=components,
                )
            )

        kinds_present = {c.kind for d in days for c in d.components}
        inclusions = sorted(f"{k} arrangements" for k in kinds_present)

        return ItineraryDraft(
            title=f"{place}: {theme_bits}",
            theme=f"A {theme_bits} journey through {place}.",
            region=place,
            duration_days=days_n,
            duration_nights=nights,
            overview=(
                f"A {days_n}-day draft for {place} built from the top-ranked "
                "candidates, weighted to the client's priorities. Review and refine "
                "in the builder; the engine prices it."
            ),
            days=days,
            inclusions=inclusions,
            exclusions=["International/domestic flights", "Personal expenses", "+5% GST"],
            ops_notes=[
                "Scaffold (stub) draft — enable the live model for RootsVida-voice prose.",
                "Obtain confirmed rates for all stays before issuing a quote.",
            ],
            sources=[],
        )
