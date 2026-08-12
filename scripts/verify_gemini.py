"""Verify the live Gemini provider end-to-end — without exposing the key.

Reads GEMINI_API_KEY (and the RV_ENABLE_LLM / RV_LLM_PROVIDER flags) from the
repo-root .env via Settings; it never reads or prints the key value itself. Run it
after: (1) adding those to .env, (2) installing the SDK
(`pip install -e "services/domain-svc[llm]"`).

    python scripts/verify_gemini.py

Prints the parsed intake + a drafted itinerary so you can confirm the real model
returns valid structured output before we wire it into the live app.
"""

from __future__ import annotations

import sys
from pathlib import Path

SVC_DIR = Path(__file__).resolve().parents[1] / "services" / "domain-svc"
sys.path.insert(0, str(SVC_DIR))

from app.config import get_settings
from app.llm import DraftBrief, DraftCandidate, get_provider


def main() -> None:
    provider = get_provider(get_settings())
    print(f"Active provider: {provider.name}")
    if provider.name != "gemini":
        print(
            "Gemini is not active. In .env set RV_ENABLE_LLM=true, "
            "RV_LLM_PROVIDER=gemini, and GEMINI_API_KEY=<your key>, then re-run."
        )
        return

    print("\n1) Parsing a sample pasted intake…")
    parsed = provider.parse_intake(
        "5-day wellness trip to Rishikesh for 5 people, homestay, budget 300000, "
        "travellers from the US, ages 25-40, arriving by flights + tempo traveller."
    )
    print(f"   destination={parsed.destination} days={parsed.duration_days} "
          f"budget={parsed.budget_inr} themes={parsed.themes}")

    print("\n2) Drafting an itinerary from a brief + one candidate…")
    brief = DraftBrief(
        destination="Rishikesh", duration_days=3, group_size=5,
        themes=["Wellness", "Yoga"], tier="Homestay",
        candidates=[DraftCandidate(id="s1", name="Riverside Retreat", kind="stay", score=90)],
    )
    draft = provider.draft(brief)
    print(f"   title: {draft.title}")
    print(f"   {len(draft.days)} days, {len(draft.inclusions)} inclusions")
    for d in draft.days:
        print(f"    Day {d.day_number}: {d.title} — {len(d.components)} components")
    print("\nOK — live Gemini returned a valid ItineraryDraft.")


if __name__ == "__main__":
    main()
