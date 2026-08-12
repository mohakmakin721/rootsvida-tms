"""Phase 5 (5a-M3) — LLM layer: factory + deterministic stub provider. No DB/SDK."""

from __future__ import annotations

from types import SimpleNamespace

from app.llm import (
    DraftBrief,
    DraftCandidate,
    ItineraryDraft,
    StubProvider,
    get_provider,
)


def _brief(days: int = 3, cands: list[DraftCandidate] | None = None) -> DraftBrief:
    return DraftBrief(
        destination="Rishikesh", duration_days=days, group_size=5,
        themes=["Wellness", "Yoga"], candidates=cands or [],
    )


# --- factory --------------------------------------------------------------

def test_factory_returns_stub_when_disabled() -> None:
    s = SimpleNamespace(rv_enable_llm=False, rv_llm_provider="stub",
                        gemini_api_key="", rv_gemini_model="x")
    assert isinstance(get_provider(s), StubProvider)


def test_factory_stub_when_gemini_selected_but_no_key() -> None:
    # Guard: selecting gemini without a key must NOT try to import the SDK.
    s = SimpleNamespace(rv_enable_llm=True, rv_llm_provider="gemini",
                        gemini_api_key="", rv_gemini_model="x")
    assert isinstance(get_provider(s), StubProvider)


# --- stub draft -----------------------------------------------------------

def test_draft_has_requested_days() -> None:
    d = StubProvider().draft(_brief(days=5))
    assert d.duration_days == 5
    assert len(d.days) == 5
    assert d.duration_nights == 4
    assert [day.day_number for day in d.days] == [1, 2, 3, 4, 5]


def test_draft_uses_ranked_candidates() -> None:
    cands = [
        DraftCandidate(id="s1", name="Aloha Homestay", kind="stay", score=90),
        DraftCandidate(id="a1", name="Sunrise Yoga", kind="activity", score=80),
    ]
    d = StubProvider().draft(_brief(days=2, cands=cands))
    titles = [c.title for day in d.days for c in day.components]
    assert "Aloha Homestay" in titles
    assert "Sunrise Yoga" in titles
    stays = [c for day in d.days for c in day.components if c.kind == "stay"]
    assert stays and stays[0].supplier_id == "s1"


def test_stub_invents_no_prices() -> None:
    cands = [DraftCandidate(id="s1", name="X", kind="stay")]
    d = StubProvider().draft(_brief(cands=cands))
    assert all(
        c.estimate_amount is None for day in d.days for c in day.components
    )


def test_draft_with_no_candidates_is_valid() -> None:
    d = StubProvider().draft(_brief(days=1, cands=[]))
    assert len(d.days) == 1
    assert d.region == "Rishikesh"


def test_draft_clamps_to_at_least_one_day() -> None:
    d = StubProvider().draft(_brief(days=0))
    assert len(d.days) >= 1


def test_draft_round_trips_through_schema() -> None:
    d = StubProvider().draft(
        _brief(days=2, cands=[DraftCandidate(id="s1", name="X", kind="stay")])
    )
    assert ItineraryDraft.model_validate(d.model_dump()) == d


# --- stub parse -----------------------------------------------------------

def test_parse_intake_preserves_raw() -> None:
    p = StubProvider().parse_intake("Budget: 300000\nDays: 5")
    assert p.raw == "Budget: 300000\nDays: 5"
