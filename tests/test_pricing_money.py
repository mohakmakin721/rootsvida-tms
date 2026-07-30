"""Phase 2 M1 — money primitives (pure, no DB)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pricing.money import money, quantize, round_rupee, round_to_nearest


def test_money_rejects_float_and_bool() -> None:
    with pytest.raises(TypeError):
        money(0.1)  # a float would smuggle in 0.1000000000000000055...
    with pytest.raises(TypeError):
        money(True)  # bool is an int subclass; not a money value


def test_money_accepts_int_str_decimal() -> None:
    assert money(5900) == Decimal(5900)
    assert money("4555.56") == Decimal("4555.56")
    assert money(Decimal(7300)) == Decimal(7300)


def test_money_is_exact_where_float_is_not() -> None:
    assert money("0.1") + money("0.2") == Decimal("0.3")
    assert 0.1 + 0.2 != 0.3  # the float trap this engine avoids


def test_quantize_is_half_up() -> None:
    # Exact Decimal 1.005 rounds UP to 1.01 (a float 1.005 would round to 1.00).
    assert quantize(Decimal("1.005")) == Decimal("1.01")
    assert quantize(Decimal("2.675")) == Decimal("2.68")


def test_round_rupee_half_up_not_bankers() -> None:
    assert round_rupee(Decimal("0.5")) == Decimal(1)
    assert round_rupee(Decimal("1.5")) == Decimal(2)
    assert round_rupee(Decimal("2.5")) == Decimal(3)  # not 2 (banker's)
    assert round_rupee(Decimal("65596.96")) == Decimal(65597)


def test_round_to_nearest_hundred() -> None:
    assert round_to_nearest(Decimal(169650), Decimal(100)) == Decimal(169700)
    assert round_to_nearest(Decimal(169749), Decimal(100)) == Decimal(169700)
    assert round_to_nearest(Decimal(169750), Decimal(100)) == Decimal(169800)


def test_round_to_nearest_rejects_nonpositive_step() -> None:
    with pytest.raises(ValueError):
        round_to_nearest(Decimal(100), Decimal(0))
