"""Phase 5 (5a-M2) — the pure weighted-priority rule engine. No DB required."""

from __future__ import annotations

from decimal import Decimal

from app.planning import (
    BASE_WEIGHTS,
    Candidate,
    IntakeSignals,
    Priority,
    derive_weights,
    rank,
    score,
    theme_mix,
)

P = Priority


def _sums_to_100(weights: dict[Priority, float]) -> bool:
    return abs(sum(weights.values()) - 100.0) < 0.05


# --- base + normalisation -------------------------------------------------

def test_base_weights_sum_to_100() -> None:
    assert abs(sum(BASE_WEIGHTS.values()) - 100.0) < 1e-9


def test_empty_intake_normalises_base() -> None:
    w = derive_weights(IntakeSignals())
    assert _sums_to_100(w)
    # Experience-match stays the dominant default.
    assert max(w, key=lambda p: w[p]) is P.EXPERIENCE_MATCH


def test_weights_always_positive_and_normalised() -> None:
    w = derive_weights(
        IntakeSignals(
            themes=["Wellness", "Yoga", "Festival", "Trekking"],
            tier="Luxury Hotel", budget_inr=Decimal("50000"),
            group_size=5, duration_days=5, age_band="40 and above",
            transport=["Car", "Tempo Traveler"],
        )
    )
    assert _sums_to_100(w)
    assert all(v >= 1.0 for v in w.values())


# --- tier -----------------------------------------------------------------

def test_luxury_raises_comfort_lowers_budget() -> None:
    base = derive_weights(IntakeSignals())
    lux = derive_weights(IntakeSignals(tier="Luxury Hotel"))
    assert lux[P.COMFORT] > base[P.COMFORT]
    assert lux[P.BUDGET_FIT] < base[P.BUDGET_FIT]


def test_homestay_raises_budget_and_authenticity() -> None:
    base = derive_weights(IntakeSignals())
    home = derive_weights(IntakeSignals(tier="Homestays"))
    assert home[P.BUDGET_FIT] > base[P.BUDGET_FIT]
    assert home[P.AUTHENTICITY] > base[P.AUTHENTICITY]
    assert home[P.COMFORT] < base[P.COMFORT]


# --- budget tightness -----------------------------------------------------

def test_tight_budget_raises_budget_fit() -> None:
    base = derive_weights(IntakeSignals())
    tight = derive_weights(
        IntakeSignals(budget_inr=Decimal("50000"), group_size=5, duration_days=5)
    )  # ₹2,000 pppd → below LOW
    assert tight[P.BUDGET_FIT] > base[P.BUDGET_FIT]


def test_generous_budget_raises_comfort() -> None:
    base = derive_weights(IntakeSignals())
    lush = derive_weights(
        IntakeSignals(budget_inr=Decimal("800000"), group_size=4, duration_days=5)
    )  # ₹40,000 pppd → above HIGH
    assert lush[P.COMFORT] > base[P.COMFORT]
    assert lush[P.BUDGET_FIT] < base[P.BUDGET_FIT]


# --- age band (regression: 25-40 must NOT read as 40+) --------------------

def test_older_group_raises_pace() -> None:
    base = derive_weights(IntakeSignals())
    older = derive_weights(IntakeSignals(age_band="40 and above"))
    assert older[P.PACE] > base[P.PACE]


def test_mid_age_band_does_not_trigger_pace() -> None:
    base = derive_weights(IntakeSignals())
    mid = derive_weights(IntakeSignals(age_band="25-40"))
    assert mid[P.PACE] == base[P.PACE]


def test_young_group_lowers_pace() -> None:
    base = derive_weights(IntakeSignals())
    young = derive_weights(IntakeSignals(age_band="18-24"))
    assert young[P.PACE] < base[P.PACE]


# --- transport ------------------------------------------------------------

def test_ground_only_raises_proximity() -> None:
    base = derive_weights(IntakeSignals())
    ground = derive_weights(IntakeSignals(transport=["Car", "Tempo Traveler"]))
    assert ground[P.PROXIMITY] > base[P.PROXIMITY]


def test_flights_do_not_raise_proximity() -> None:
    base = derive_weights(IntakeSignals())
    flying = derive_weights(IntakeSignals(transport=["Flights", "Tempo Traveler"]))
    assert flying[P.PROXIMITY] <= base[P.PROXIMITY]


# --- themes ---------------------------------------------------------------

def test_many_themes_raise_experience_match() -> None:
    base = derive_weights(IntakeSignals())
    themed = derive_weights(
        IntakeSignals(themes=["Wellness", "Yoga", "Festival", "Trekking"])
    )
    assert themed[P.EXPERIENCE_MATCH] > base[P.EXPERIENCE_MATCH]


# --- scoring --------------------------------------------------------------

def test_missing_scores_are_neutral() -> None:
    w = derive_weights(IntakeSignals())
    assert score(Candidate(id="x", name="Blank"), w) == 50.0


def test_higher_priority_match_scores_higher() -> None:
    w = {P.EXPERIENCE_MATCH: 80.0, P.COMFORT: 20.0}
    good = Candidate(id="a", name="On-theme", scores={P.EXPERIENCE_MATCH: 90})
    poor = Candidate(id="b", name="Off-theme", scores={P.EXPERIENCE_MATCH: 10})
    assert score(good, w) > score(poor, w)


# --- ranking --------------------------------------------------------------

def test_rank_sorts_best_first() -> None:
    w = {P.EXPERIENCE_MATCH: 100.0}
    cands = [
        Candidate(id="lo", name="lo", scores={P.EXPERIENCE_MATCH: 20}),
        Candidate(id="hi", name="hi", scores={P.EXPERIENCE_MATCH: 95}),
        Candidate(id="mid", name="mid", scores={P.EXPERIENCE_MATCH: 60}),
    ]
    ranked = rank(cands, w)
    assert [sc.candidate.id for sc in ranked] == ["hi", "mid", "lo"]


def test_rank_filters_over_budget() -> None:
    w = {P.EXPERIENCE_MATCH: 100.0}
    cands = [
        Candidate(id="cheap", name="c", scores={P.EXPERIENCE_MATCH: 50},
                  cost=Decimal("4000")),
        Candidate(id="pricey", name="p", scores={P.EXPERIENCE_MATCH: 99},
                  cost=Decimal("30000")),
    ]
    ranked = rank(cands, w, max_cost=Decimal("10000"))
    assert [sc.candidate.id for sc in ranked] == ["cheap"]


def test_rank_is_stable_on_ties() -> None:
    w = {P.EXPERIENCE_MATCH: 100.0}
    cands = [
        Candidate(id="first", name="1", scores={P.EXPERIENCE_MATCH: 50}),
        Candidate(id="second", name="2", scores={P.EXPERIENCE_MATCH: 50}),
    ]
    ranked = rank(cands, w)
    assert [sc.candidate.id for sc in ranked] == ["first", "second"]


# --- theme mix ------------------------------------------------------------

def test_theme_mix_equal_split_sums_100() -> None:
    mix = theme_mix(["Wellness", "Trekking", "Festival"])
    assert abs(sum(mix.values()) - 100.0) < 0.05
    assert mix["Wellness"] == mix["Trekking"] == mix["Festival"]


def test_theme_mix_empty() -> None:
    assert theme_mix([]) == {}


def test_theme_mix_importance_weighting() -> None:
    mix = theme_mix(["Wellness", "Festival"], importance={"Wellness": 3.0, "Festival": 1.0})
    assert mix["Wellness"] > mix["Festival"]
    assert abs(sum(mix.values()) - 100.0) < 0.05


# --- worked example (spec sanity) -----------------------------------------

def test_rishikesh_sample_is_experience_led() -> None:
    w = derive_weights(
        IntakeSignals(
            themes=["Wellness & De-stress", "Yoga and Wellness",
                    "Festival", "Trekking and Hiking"],
            tier="Homestays", budget_inr=Decimal("300000"),
            group_size=5, duration_days=5, age_band="25-40",
            transport=["Flights", "Tempo Traveler"],
        )
    )
    assert _sums_to_100(w)
    assert max(w, key=lambda p: w[p]) is P.EXPERIENCE_MATCH
