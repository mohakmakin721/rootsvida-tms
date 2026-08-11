"""Google Gemini provider (Phase 5, 5a-M3) — scaffolded, dormant until configured.

Uses the `google-genai` SDK (optional dependency, lazy-imported) with structured
JSON output validated against our Pydantic schema. Not exercised by tests; it goes
live only when RV_ENABLE_LLM=true, provider=gemini, and GEMINI_API_KEY is set, and is
first verified on a Vercel/Render preview — never blind in production.

Guardrails baked into the system prompt: propose structure + prose and pick from the
given candidates; any price is an ESTIMATE only (source llm_estimate); the
deterministic engine owns all totals.
"""

from __future__ import annotations

from typing import Any

from app.llm.base import LLMProvider
from app.llm.schema import DraftBrief, IntakeParse, ItineraryDraft

_SYSTEM = (
    "You are RootsVida's itinerary designer. Draft small-group, culturally immersive "
    "trips in RootsVida's warm, sensory, specific voice, and return STRUCTURED JSON "
    "only, matching the given schema. Prefer the CANDIDATE suppliers provided (set "
    "supplier_id/supplier_name from them). You may include a rough per-item "
    "estimate_amount, but treat it as an UNVERIFIED estimate — never a final price, "
    "never a total; the pricing engine owns all arithmetic. Map every paid item to a "
    "component. Use ONLY these kinds: stay, transport, activity, guide, meal, "
    "permit, misc (an airport/transfer is 'transport'). Use ONLY these allocation "
    "values: all_pax, by_pax_class, per_segment, per_pax_direct, fixed_group. Flag "
    "permits, seasonality, "
    "altitude and long drives in ops_notes.\n"
    "TAILOR TO THE FULL BRIEF: destination, duration, themes, budget_inr, tier, "
    "age_band, transport, and the traveller mix (pax_summary, occupancy_summary, "
    "has_foreign). When has_foreign is true, monument entry tickets and guide fees "
    "usually differ for foreign vs Indian travellers — model those with allocation "
    "'by_pax_class' and call it out in ops_notes. Pick stays that suit the occupancy "
    "mix (single/double/triple) and the tier + budget; keep an older age_band's pace "
    "gentle. Use `origin` (the travellers' start point) to plan the outbound and "
    "return TRANSPORT from origin to destination (e.g. a flight or drive origin→"
    "destination and back) plus local airport/station transfers. If the trip is "
    "international (travellers crossing a border — e.g. foreign nationals, or origin "
    "and destination in different countries), include a 'Visa' cost component (kind "
    "misc, allocation per_pax_direct or by_pax_class) and note it in ops_notes. "
    "Finally, obey the free-text `notes` (the owner's constraints / must-include / "
    "must-exclude points) — they override defaults. Every day and choice should "
    "visibly reflect these inputs."
)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, review: bool = True) -> None:
        self.api_key = api_key
        self.model = model
        self.review = review
        self._cli: Any = None

    def _client(self) -> Any:
        # Cache the client for the provider's lifetime. Creating it per-call without
        # holding a reference lets it be garbage-collected/closed mid-request (the
        # SDK's "Cannot send a request, as the client has been closed") on retries.
        if self._cli is None:
            from google import genai  # lazy: optional dependency

            self._cli = genai.Client(api_key=self.api_key)
        return self._cli

    def _generate(self, prompt: str, schema: type[Any]) -> str:
        from google.genai import types  # lazy

        client = self._client()
        resp = client.models.generate_content(
            model=self.model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        return str(resp.text)

    def parse_intake(self, text: str) -> IntakeParse:
        prompt = (
            "Extract the trip-intake fields from this client form response. Leave "
            f"unknown fields null.\n\n{text}"
        )
        parsed = IntakeParse.model_validate_json(self._generate(prompt, IntakeParse))
        parsed.raw = text
        return parsed

    def draft(self, brief: DraftBrief) -> ItineraryDraft:
        prompt = (
            "Draft an itinerary for this brief:\n\n"
            f"{brief.model_dump_json(indent=2)}\n\n"
            "REQUIREMENTS — follow EVERY one:\n"
            "1. Prefer the highest-scoring CANDIDATES for stays/experiences.\n"
            "2. Include the MAIN long-haul travel between the origin CITY and the "
            "destination CITY as transport components: the outbound leg (e.g. a flight "
            "Delhi→Paris) on day 1 and the return (Paris→Delhi) on the final day — "
            "prefer a sensible balance of direct and affordable — IN ADDITION to local "
            "airport/station transfers and any inter-city legs within the trip.\n"
            "3. If international (has_foreign is true, or origin and destination are in "
            "different countries), ADD a 'Visa' cost component (kind misc) and an "
            "ops_note about it.\n"
            "4. OBEY the `notes` constraints EXACTLY: include everything they say to "
            "include (e.g. a farewell dinner) and avoid everything they say to avoid.\n"
            "5. For foreign travellers, price monument tickets and guides with "
            "allocation 'by_pax_class'.\n"
            "6. REALITY CHECK before you answer: every estimate_amount must be a "
            "realistic current market price for that item at the destination and tier, "
            "in INR; the day-by-day sequence must be logistically feasible (sensible "
            "travel times and opening hours, nothing physically impossible); and the "
            "whole plan must reflect the priority weights. Silently fix anything "
            "unrealistic before returning."
        )
        initial = ItineraryDraft.model_validate_json(self._generate(prompt, ItineraryDraft))
        return self._review(brief, initial) if self.review else initial

    def _review(self, brief: DraftBrief, draft: ItineraryDraft) -> ItineraryDraft:
        """Second pass: the model critiques its own draft against the brief and fixes
        gaps a one-shot flash model tends to miss (long-haul flights, must-includes,
        unrealistic prices). Returns a corrected ItineraryDraft (unchanged if fine)."""
        prompt = (
            "Review this DRAFT itinerary against the BRIEF and fix EVERY issue, then "
            "return the corrected ItineraryDraft (same schema):\n"
            "- Missing long-haul transport between the origin and destination cities: "
            "add the outbound flight (origin→destination) on day 1 and the return on "
            "the last day if absent.\n"
            "- Any must-include in `notes` that is missing → add it; any must-exclude "
            "still present → remove it.\n"
            "- A missing 'Visa' component when the trip is international → add it.\n"
            "- Unrealistic estimate_amount values → correct to realistic INR market "
            "prices; infeasible travel times/sequencing → fix.\n"
            "If the draft is already correct, return it unchanged.\n\n"
            f"BRIEF:\n{brief.model_dump_json(indent=2)}\n\n"
            f"DRAFT:\n{draft.model_dump_json(indent=2)}"
        )
        return ItineraryDraft.model_validate_json(self._generate(prompt, ItineraryDraft))
