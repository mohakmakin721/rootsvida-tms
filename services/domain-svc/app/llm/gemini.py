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
    "gentle. Use `origin` (the travellers' start point) to plan arrival/return "
    "transport and transfers (e.g. flights or drive from origin, airport pickup). "
    "Every day and choice should visibly reflect these inputs."
)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
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
            "Draft an itinerary for this brief. CANDIDATES are pre-ranked by the "
            "client's priorities — prefer the highest-scoring ones.\n\n"
            f"{brief.model_dump_json(indent=2)}"
        )
        return ItineraryDraft.model_validate_json(self._generate(prompt, ItineraryDraft))
