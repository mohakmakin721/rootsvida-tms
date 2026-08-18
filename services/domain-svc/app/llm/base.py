"""The LLM provider interface (Phase 5, 5a-M3).

One narrow contract so the stub, Gemini, and (later) Anthropic are interchangeable
and the rest of the app never imports a vendor SDK directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.llm.schema import DraftBrief, IntakeParse, ItineraryDraft


class LLMProvider(ABC):
    """Two tasks: parse a pasted intake, and draft a structured itinerary."""

    name: str = "base"

    @abstractmethod
    def parse_intake(self, text: str) -> IntakeParse:
        """Turn a pasted client-form response into structured intake fields."""

    @abstractmethod
    def draft(self, brief: DraftBrief) -> ItineraryDraft:
        """Turn a brief + ranked candidates into a structured itinerary draft."""

    def refine(
        self, brief: DraftBrief, draft: ItineraryDraft, instruction: str
    ) -> ItineraryDraft:
        """Apply a free-text change request to an existing draft, returning the
        updated draft. Default is a no-op (providers without chat just echo the draft);
        GeminiProvider overrides it."""
        return draft
