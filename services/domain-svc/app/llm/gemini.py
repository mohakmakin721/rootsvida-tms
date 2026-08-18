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
    "values: all_pax, by_pax_class, per_segment, per_pax_direct, fixed_group.\n"
    "\n"
    "PER-DAY CATEGORY CHECKLIST — this is the core of the job. For EVERY single day, "
    "walk all seven categories below and add a component for each that applies to that "
    "day. Do not leave a day thin: a real traveller must sleep, eat and move every "
    "day, so those are almost never empty.\n"
    "  • STAY (kind stay) — the guest sleeps somewhere every night. Add a stay for "
    "each night of the trip (a D-day trip has D-1 nights: nights on days 1..D-1; on "
    "the final day the guest checks out and departs, so usually no new stay). Match "
    "the occupancy mix (single/double/triple), tier and budget.\n"
    "  • MEAL (kind meal) — the guest eats every day. Add the meals you are including "
    "for that day (per the meal plan — e.g. breakfast at the stay, a signature lunch/"
    "dinner). Every day has at least one meal component.\n"
    "  • TRANSPORT (kind transport) — three things: (a) the MAIN long-haul leg from "
    "origin CITY to destination CITY on day 1, and the RETURN destination→origin on "
    "the final day, each priced for the chosen mode — FLIGHT, TRAIN or CAR (give a "
    "realistic current INR estimate for that mode); (b) LOCAL transport EVERY day "
    "(cab / coach / airport or station transfer) for that day's movements; (c) any "
    "inter-city legs within the trip.\n"
    "  • GUIDE (kind guide) — add ONLY on days that visit monuments / heritage sites / "
    "museums, or whenever travellers are foreign (a licensed guide is often required "
    "and priced differently for foreigners). Not every day needs a guide.\n"
    "  • ACTIVITY (kind activity) — each day include the signature experience(s) in "
    "and around that place (workshops, treks, safaris, food walks, boat rides, "
    "performances) that give the holistic feel of the destination.\n"
    "  • PERMIT (kind permit) — NON-NEGOTIABLE where a place requires one. Inner-line / "
    "border / eco / protected-area permits: e.g. the Attari–Wagah border ceremony "
    "near Amritsar, Harshil / Gangotri & the Nelong valley in Uttarakhand, Nathu La "
    "in Sikkim, Nubra & Pangong in Ladakh, national-park / tiger-reserve entry. If a "
    "day's place needs a permit you MUST add a permit component AND flag it in "
    "ops_notes. NEVER silently omit a required permit.\n"
    "  • MISC (kind misc) — add a small operational buffer line each day or once for "
    "the trip (tips, drinking water, porterage, SIM, contingencies) so small "
    "operational costs can be topped up after the quote goes out. A Visa is a misc "
    "component too.\n"
    "\n"
    "ALLOCATION & PER-PERSON PRICING — set `allocation` so the engine multiplies by "
    "the right head-count, and price `estimate_amount` to MATCH that allocation:\n"
    "  • PER PERSON (allocation 'per_pax_direct', or 'by_pax_class' when foreign vs "
    "Indian differ): FLIGHTS and TRAINS (ticketed per seat), monument/activity entry "
    "tickets, and per-head guide fees. estimate_amount = the price for ONE traveller; "
    "the engine multiplies by the number of travellers.\n"
    "  • SHARED by the whole group (allocation 'all_pax'): a CAR / TEMPO TRAVELLER / "
    "private coach and other whole-vehicle hire, a private guide booked per day, and "
    "a group permit. estimate_amount = the WHOLE-VEHICLE / whole-group total (do NOT "
    "pre-multiply by pax). A stay room rate is per room for its occupancy.\n"
    "So a 5-pax group flying costs 5 × the per-seat fare, but one tempo traveller is a "
    "single shared amount — reflect that in the allocation, never by inflating a "
    "per-person number.\n"
    "\n"
    "BUDGET FIT — `budget_inr` is the group's TOTAL budget for the whole trip. Design "
    "to FIT WITHIN it: choose stays/transport/activities whose estimated grand total "
    "(per-person items × travellers + shared items) stays at or under budget_inr. If "
    "the requested tier genuinely cannot fit, return the leanest sensible plan AND add "
    "an ops_note stating it exceeds the budget and by roughly how much, so the owner "
    "is warned before quoting.\n"
    "\n"
    "TAILOR TO THE FULL BRIEF: destination, duration, themes, budget_inr, tier, "
    "age_band, transport, and the traveller mix (pax_summary, occupancy_summary, "
    "has_foreign). When has_foreign is true, monument entry tickets and guide fees "
    "usually differ for foreign vs Indian travellers — model those with allocation "
    "'by_pax_class' and call it out in ops_notes. Pick stays that suit the occupancy "
    "mix (single/double/triple) and the tier + budget; keep an older age_band's pace "
    "gentle. Use `origin` (the travellers' start point) to plan the outbound and "
    "return TRANSPORT from origin to destination (flight/train/car, priced) plus "
    "local airport/station transfers. If the trip is international (travellers "
    "crossing a border — e.g. foreign nationals, or origin and destination in "
    "different countries), include a 'Visa' cost component (kind misc, allocation "
    "per_pax_direct or by_pax_class) and note it in ops_notes. Flag permits, "
    "seasonality, altitude and long drives in ops_notes. Finally, obey the free-text "
    "`notes` (the owner's constraints / must-include / must-exclude points) — they "
    "override defaults. Every day and choice should visibly reflect these inputs."
)


_RESEARCH_SYSTEM = (
    "You are a travel-cost researcher. Use Google Search to find CURRENT, real-world "
    "prices and requirements. Answer with short factual bullet points only — no prose, "
    "no itinerary. Give approximate figures in INR and name the item each figure is for."
)


def _grounding_urls(resp: Any) -> list[str]:
    """Pull citation URLs out of a grounded response's metadata (defensive: the SDK's
    shape varies by version, so every access is guarded and failures yield [])."""
    urls: list[str] = []
    try:
        for cand in resp.candidates or []:
            meta = getattr(cand, "grounding_metadata", None)
            for chunk in getattr(meta, "grounding_chunks", None) or []:
                uri = getattr(getattr(chunk, "web", None), "uri", None)
                if uri:
                    urls.append(str(uri))
    except Exception:
        return []
    return list(dict.fromkeys(urls))


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self, api_key: str, model: str, review: bool = True, grounding: bool = False
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.review = review
        self.grounding = grounding
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

    def _research(self, brief: DraftBrief) -> tuple[str, list[str]]:
        """Option A grounding pass: search Google for live costs and return
        (research_notes, source_urls). The google_search tool CANNOT be combined with
        response_schema, so this returns free text we fold into the structured draft
        prompt — the draft itself stays schema-constrained. Best-effort: on any error
        (SDK too old, quota, network) it returns empty so drafting still proceeds."""
        try:
            from google.genai import types  # lazy

            client = self._client()
            query = (
                "Find CURRENT approximate costs (INR) and requirements for this trip. "
                "List concise bullets covering: the origin->destination fare BOTH ways "
                "for flight, train and car; representative per-night stay rates at the "
                "given tier; visa fee if international; monument/activity entry tickets "
                "(note foreigner vs Indian where they differ); local transport per day; "
                "a licensed guide per day; and any MANDATORY permits (name them).\n\n"
                f"{brief.model_dump_json(indent=2)}"
            )
            resp = client.models.generate_content(
                model=self.model,
                contents=[query],
                config=types.GenerateContentConfig(
                    system_instruction=_RESEARCH_SYSTEM,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            return str(resp.text or ""), _grounding_urls(resp)
        except Exception:
            return "", []

    def parse_intake(self, text: str) -> IntakeParse:
        prompt = (
            "Extract the trip-intake fields from this client form response. Leave "
            f"unknown fields null.\n\n{text}"
        )
        parsed = IntakeParse.model_validate_json(self._generate(prompt, IntakeParse))
        parsed.raw = text
        return parsed

    def draft(self, brief: DraftBrief) -> ItineraryDraft:
        research, sources = self._research(brief) if self.grounding else ("", [])
        research_block = (
            "LIVE MARKET RESEARCH (from a web search — treat these as the CURRENT "
            "reference figures and use them for estimate_amount where relevant; they "
            "override your own guesses, but remain unverified estimates):\n"
            f"{research}\n\n"
            if research.strip()
            else ""
        )
        prompt = (
            "Draft an itinerary for this brief:\n\n"
            f"{brief.model_dump_json(indent=2)}\n\n"
            f"{research_block}"
            "REQUIREMENTS — follow EVERY one:\n"
            "1. RUN THE PER-DAY CATEGORY CHECKLIST for EVERY day (stay, meal, "
            "transport, guide, activity, permit, misc). For each day, add a component "
            "for every category that applies. Every day must have at least a stay "
            "(except the departure day), a meal and local transport; add guide, "
            "activity, permit and misc wherever they apply. Do not leave any day "
            "with only a narrative and no components.\n"
            "2. Prefer the highest-scoring CANDIDATES for stays/experiences.\n"
            "3. ORIGIN↔DESTINATION FARES: include the MAIN long-haul leg between the "
            "origin CITY and the destination CITY as transport components — the "
            "outbound on day 1 and the return on the final day — each PRICED for the "
            "chosen mode (flight / train / car) with a realistic current INR "
            "estimate_amount. Prefer a sensible balance of direct and affordable. This "
            "is IN ADDITION to local airport/station transfers and any inter-city legs.\n"
            "4. PERMITS ARE NON-NEGOTIABLE: if any day's place requires an inner-line / "
            "border / eco / protected-area permit (e.g. Attari–Wagah, Harshil/Nelong, "
            "Nathu La, Nubra/Pangong, park entry), you MUST add a permit component that "
            "day and an ops_note. Never omit a required permit.\n"
            "5. If international (has_foreign is true, or origin and destination are in "
            "different countries), ADD a 'Visa' cost component (kind misc) and an "
            "ops_note about it.\n"
            "6. OBEY the `notes` constraints EXACTLY: include everything they say to "
            "include (e.g. a farewell dinner) and avoid everything they say to avoid.\n"
            "7. For foreign travellers, price monument tickets and guides with "
            "allocation 'by_pax_class'.\n"
            "8. REALITY CHECK before you answer: every estimate_amount must be a "
            "realistic current market price for that item at the destination and tier, "
            "in INR; the day-by-day sequence must be logistically feasible (sensible "
            "travel times and opening hours, nothing physically impossible); and the "
            "whole plan must reflect the priority weights. Silently fix anything "
            "unrealistic before returning."
        )
        initial = ItineraryDraft.model_validate_json(self._generate(prompt, ItineraryDraft))
        result = self._review(brief, initial) if self.review else initial
        if sources:  # keep the web-search citations on the final draft
            result.sources = list(dict.fromkeys([*result.sources, *sources]))
        return result

    def refine(
        self, brief: DraftBrief, draft: ItineraryDraft, instruction: str
    ) -> ItineraryDraft:
        """Apply the owner's free-text change to an existing draft and return the whole
        updated ItineraryDraft (same schema). Keeps everything not mentioned intact,
        obeys the same rules (per-day categories, allocation, budget) as a fresh draft."""
        prompt = (
            "Here is an existing itinerary DRAFT and a CHANGE REQUEST from the owner. "
            "Apply the change and return the COMPLETE updated ItineraryDraft (same "
            "schema). Change ONLY what the request implies; keep everything else exactly "
            "as it is (same days, titles, components, estimates) unless the change makes "
            "them inconsistent. Keep obeying the per-day category, allocation "
            "(per-person vs shared) and budget rules.\n\n"
            f"BRIEF:\n{brief.model_dump_json(indent=2)}\n\n"
            f"CURRENT DRAFT:\n{draft.model_dump_json(indent=2)}\n\n"
            f"CHANGE REQUEST:\n{instruction}"
        )
        return ItineraryDraft.model_validate_json(self._generate(prompt, ItineraryDraft))

    def _review(self, brief: DraftBrief, draft: ItineraryDraft) -> ItineraryDraft:
        """Second pass: the model critiques its own draft against the brief and fixes
        gaps a one-shot flash model tends to miss (long-haul flights, must-includes,
        unrealistic prices). Returns a corrected ItineraryDraft (unchanged if fine)."""
        prompt = (
            "Review this DRAFT itinerary against the BRIEF and fix EVERY issue, then "
            "return the corrected ItineraryDraft (same schema):\n"
            "- PER-DAY CATEGORY GAPS: for every day, re-check the seven categories "
            "(stay, meal, transport, guide, activity, permit, misc). A night with no "
            "stay (before the departure day), a day with no meal, or a day with no "
            "local transport is a gap → add the missing component.\n"
            "- Missing origin↔destination fares: add the outbound main leg "
            "(origin→destination, flight/train/car, priced) on day 1 and the return "
            "on the last day if absent.\n"
            "- A required PERMIT that is missing for any day's place (border / "
            "inner-line / eco / park permit) → add the permit component and an "
            "ops_note.\n"
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
