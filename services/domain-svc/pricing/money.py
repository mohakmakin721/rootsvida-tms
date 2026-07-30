"""Money primitives — the exact-arithmetic foundation (Part 2 §5).

Two rules the whole engine depends on:

1. **`Decimal`, never `float`.** Floats reintroduce binary rounding error — the
   very thing this engine exists to eliminate. `money()` refuses a `float` so an
   inexact value can never enter a calculation by accident.
2. **`ROUND_HALF_UP`, once.** Matches Excel/Tally (the source workbook and the
   accountant's ledger). Rounding happens at a policy boundary, never on an
   intermediate — that is how a ₹0.01 drift becomes a ₹40 discrepancy on a group.

Nothing here rounds implicitly; callers round explicitly with `quantize`,
`round_to_nearest`, or `round_rupee` at the boundary they choose.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# A monetary amount. Kept as a plain `Decimal` alias so it composes with the
# stdlib, while signatures still read as "money" rather than "some number".
Money = Decimal

Numeric = int | str | Decimal

TWO_PLACES = Decimal("0.01")
WHOLE = Decimal("1")


def money(value: Numeric) -> Money:
    """Build a money `Decimal` from an int, string, or Decimal.

    Rejects `float`: `money(0.1)` would smuggle in `0.1000000000000000055…`.
    Pass a string (`money("0.1")`) or an int instead.
    """
    if isinstance(value, (bool, float)):
        raise TypeError(
            f"money() rejects {type(value).__name__}; pass int, str or Decimal to stay exact"
        )
    return Decimal(value)


def quantize(value: Decimal, places: Decimal = TWO_PLACES) -> Money:
    """Round to `places` (default 2 dp) with ROUND_HALF_UP."""
    return value.quantize(places, rounding=ROUND_HALF_UP)


def round_rupee(value: Decimal) -> Money:
    """Round to whole rupees (0 dp), ROUND_HALF_UP — the workbook's `ROUND(x, 0)`."""
    return value.quantize(WHOLE, rounding=ROUND_HALF_UP)


def round_to_nearest(value: Decimal, step: Decimal) -> Money:
    """Round to the nearest multiple of `step` (e.g. 100), ROUND_HALF_UP.

    Used by the `gross_nearest_100` invoice mode: 169,650 → 169,700.
    """
    if step <= 0:
        raise ValueError("step must be positive")
    return (value / step).quantize(WHOLE, rounding=ROUND_HALF_UP) * step
