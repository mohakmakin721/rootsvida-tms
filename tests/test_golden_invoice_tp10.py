"""Phase 2 M6 — GOLDEN FIXTURE: invoice REPL/2627/TP10.

The second non-negotiable acceptance test (plan §1.4, Part 2 §5). Reverse-
engineered from Sample_invoice.pdf — a ₹1,69,700 Golden Triangle invoice whose
arithmetic reveals the gross_nearest_100 rounding policy:

    taxable  1,61,619.05 · CGST  4,040.48 · SGST  4,040.48 · rounding −0.01
    total  1,69,700.00

Runs in CI on every commit, forever.
"""

from __future__ import annotations

from decimal import Decimal

from pricing.model import TaxRule, TaxTreatment
from pricing.money import money
from pricing.tax import split_tax

# HSN 998555 @ 5%, split CGST 2.5% + SGST 2.5% (intra-state, Uttarakhand).
_TP10_TAX = TaxRule(Decimal("0.05"), TaxTreatment.CGST_SGST, hsn="998555")


def test_golden_invoice_tp10() -> None:
    b = split_tax(money(169700), _TP10_TAX)

    assert b.taxable == Decimal("161619.05")
    assert b.cgst == Decimal("4040.48")
    assert b.sgst == Decimal("4040.48")
    assert b.rounding_adjustment == Decimal("-0.01")
    assert b.total == Decimal("169700.00")

    # The invariant the invoice's DB CHECK constraint also enforces (Part 2 §4.6).
    assert b.taxable + b.cgst + b.sgst + b.igst + b.rounding_adjustment == b.total
