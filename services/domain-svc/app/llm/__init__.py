"""LLM layer (Phase 5) — vendor-agnostic drafting behind one interface.

`get_provider()` returns the deterministic StubProvider unless the owner has fully
enabled a live provider (RV_ENABLE_LLM + provider + key), so the app is safe to run
and test with no key and no spend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.llm.base import LLMProvider
from app.llm.schema import (
    DraftBrief,
    DraftCandidate,
    DraftComponent,
    DraftDay,
    IntakeParse,
    ItineraryDraft,
)
from app.llm.stub import StubProvider
from app.llm.validate import enforce_day_categories

if TYPE_CHECKING:
    from app.config import Settings


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """The active LLM provider. Stub unless a live provider is fully configured."""
    from app.config import get_settings

    s = settings or get_settings()
    if s.rv_enable_llm and s.rv_llm_provider == "gemini" and s.gemini_api_key:
        from app.llm.gemini import GeminiProvider

        return GeminiProvider(
            api_key=s.gemini_api_key, model=s.rv_gemini_model,
            review=s.rv_llm_review, grounding=s.rv_llm_grounding,
        )
    return StubProvider()


__all__ = [
    "DraftBrief",
    "DraftCandidate",
    "DraftComponent",
    "DraftDay",
    "IntakeParse",
    "ItineraryDraft",
    "LLMProvider",
    "StubProvider",
    "enforce_day_categories",
    "get_provider",
]
