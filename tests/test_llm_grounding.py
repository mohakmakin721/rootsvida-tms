"""Phase 5 (5a-M8) — Option A: Google-Search grounding plumbing on GeminiProvider.

Pure tests only: the actual google_search call needs the SDK + network, so here we
cover the wiring — the flag, citation-URL extraction, and the factory pass-through.
Constructing GeminiProvider does NOT import the SDK (client is lazy), so this is safe.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.llm import get_provider
from app.llm.gemini import GeminiProvider, _grounding_urls, _is_transient


def test_grounding_flag_defaults_off_and_is_settable() -> None:
    assert GeminiProvider(api_key="k", model="m").grounding is False
    assert GeminiProvider(api_key="k", model="m", grounding=True).grounding is True


def test_factory_passes_grounding_flag() -> None:
    s = SimpleNamespace(
        rv_enable_llm=True, rv_llm_provider="gemini", gemini_api_key="k",
        rv_gemini_model="m", rv_llm_review=False, rv_llm_grounding=True,
    )
    provider = get_provider(s)
    assert isinstance(provider, GeminiProvider)
    assert provider.grounding is True


def _fake_resp(*uris: str | None) -> SimpleNamespace:
    chunks = [SimpleNamespace(web=SimpleNamespace(uri=u)) for u in uris]
    meta = SimpleNamespace(grounding_chunks=chunks)
    return SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=meta)])


def test_grounding_urls_extracts_and_dedupes() -> None:
    resp = _fake_resp("https://a.com", "https://b.com", "https://a.com", None)
    assert _grounding_urls(resp) == ["https://a.com", "https://b.com"]


def test_grounding_urls_defensive_on_garbage() -> None:
    assert _grounding_urls(SimpleNamespace()) == []
    assert _grounding_urls(SimpleNamespace(candidates=None)) == []
    assert _grounding_urls(object()) == []


class _FakeGeminiError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def test_is_transient_flags_overload_and_5xx() -> None:
    # The exact 503 the model raised under load.
    assert _is_transient(_FakeGeminiError(503, "This model is currently experiencing high demand. UNAVAILABLE"))
    assert _is_transient(_FakeGeminiError(429, "RESOURCE_EXHAUSTED"))
    assert _is_transient(Exception("503 UNAVAILABLE, please try again later"))


def test_is_transient_ignores_client_errors() -> None:
    assert not _is_transient(_FakeGeminiError(400, "invalid argument"))
    assert not _is_transient(Exception("bad api key"))
