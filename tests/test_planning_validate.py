"""Phase 5 (5a-M8) — the deterministic per-day category guarantee. Pure, no DB."""

from __future__ import annotations

from app.llm import enforce_day_categories
from app.llm.schema import DraftBrief, DraftComponent, DraftDay, ItineraryDraft


def _day(n: int, place: str, *kinds: str) -> DraftDay:
    return DraftDay(
        day_number=n, title=f"Day {n}", place=place, narrative="…",
        components=[DraftComponent(kind=k, title=f"{k} {n}") for k in kinds],
    )

def _draft(*days: DraftDay) -> ItineraryDraft:
    return ItineraryDraft(
        title="T", theme="heritage", region="Amritsar",
        duration_days=len(days), duration_nights=max(len(days) - 1, 0),
        overview="…", days=list(days),
    )


def test_fills_missing_stay_meal_transport_on_middle_day() -> None:
    draft = _draft(_day(1, "Amritsar", "stay"), _day(2, "Amritsar"), _day(3, "Amritsar", "stay"))
    out, warns = enforce_day_categories(draft, DraftBrief(destination="Amritsar"))
    day2 = next(d for d in out.days if d.day_number == 2)
    kinds = {c.kind for c in day2.components}
    assert {"stay", "meal", "transport"} <= kinds
    # placeholders carry NO price (D-0001)
    assert all(c.estimate_amount is None for c in day2.components if "review" in c.notes)
    assert any("Day 2" in w and "STAY" in w for w in warns)


def test_last_day_needs_no_new_stay() -> None:
    draft = _draft(_day(1, "Jaipur", "stay", "meal", "transport"),
                   _day(2, "Jaipur", "meal", "transport"))
    out, _ = enforce_day_categories(draft, DraftBrief(destination="Jaipur"))
    last = next(d for d in out.days if d.day_number == 2)
    assert "stay" not in {c.kind for c in last.components}


def test_adds_main_legs_when_origin_known() -> None:
    draft = _draft(_day(1, "Paris", "stay", "meal", "transport"),
                   _day(2, "Paris", "meal", "transport"))
    out, warns = enforce_day_categories(
        draft, DraftBrief(origin="Delhi", destination="Paris")
    )
    d1 = " ".join(c.title.lower() for c in out.days[0].components)
    d2 = " ".join(c.title.lower() for c in out.days[-1].components)
    # day 1 already had a transport mentioning neither Delhi nor Paris keywords → main leg added
    assert "delhi" in d1 and "paris" in d1
    assert "return" in d2
    assert any("main leg" in w for w in warns)


def test_known_permit_place_gets_permit() -> None:
    draft = _draft(_day(1, "Amritsar", "stay", "meal", "transport"),
                   _day(2, "Attari-Wagah border", "meal", "transport", "activity"))
    out, warns = enforce_day_categories(draft, DraftBrief(destination="Amritsar"))
    wagah = next(d for d in out.days if "wagah" in d.place.lower())
    assert "permit" in {c.kind for c in wagah.components}
    assert any("PERMIT" in w for w in warns)


def test_idempotent() -> None:
    draft = _draft(_day(1, "Amritsar"), _day(2, "Amritsar"))
    once, _ = enforce_day_categories(draft, DraftBrief(destination="Amritsar", origin="Delhi"))
    n1 = sum(len(d.components) for d in once.days)
    twice, _ = enforce_day_categories(once, DraftBrief(destination="Amritsar", origin="Delhi"))
    n2 = sum(len(d.components) for d in twice.days)
    assert n1 == n2


def test_visa_warning_for_international() -> None:
    draft = _draft(_day(1, "Paris", "stay", "meal", "transport", "activity"),
                   _day(2, "Paris", "meal", "transport", "activity"))
    _, warns = enforce_day_categories(
        draft, DraftBrief(origin="Delhi", destination="Paris", has_foreign=True)
    )
    assert any("Visa" in w for w in warns)
