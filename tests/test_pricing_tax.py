"""Phase 2 M6 — tax split + gross_nearest_100 (pure)."""

from __future__ import annotations

from decimal import Decimal

from pricing.model import TaxRule, TaxTreatment
from pricing.money import money
from pricing.tax import split_tax

_CGST_SGST = TaxRule(Decimal("0.05"), TaxTreatment.CGST_SGST, hsn="998555")
_IGST = TaxRule(Decimal("0.05"), TaxTreatment.IGST)
_EXPORT = TaxRule(Decimal("0.05"), TaxTreatment.EXPORT)


def test_gross_is_rounded_to_nearest_hundred() -> None:
    assert split_tax(money("169650.40"), _CGST_SGST).total == Decimal(169700)
    assert split_tax(money("169749.99"), _CGST_SGST).total == Decimal(169700)


def test_cgst_sgst_backs_out_taxable_and_reconciles() -> None:
    b = split_tax(money(169700), _CGST_SGST)
    assert b.taxable == Decimal("161619.05")
    assert b.cgst == Decimal("4040.48")
    assert b.sgst == Decimal("4040.48")
    assert b.igst == Decimal(0)
    assert b.rounding_adjustment == Decimal("-0.01")
    assert b.total == Decimal("169700.00")


def test_igst_is_a_single_levy() -> None:
    b = split_tax(money(169700), _IGST)
    assert b.taxable == Decimal("161619.05")
    assert b.igst == Decimal("8080.95")  # quantize(161619.05 * 0.05)
    assert b.cgst == Decimal(0) and b.sgst == Decimal(0)
    assert b.taxable + b.igst + b.rounding_adjustment == b.total


def test_export_is_zero_rated() -> None:
    b = split_tax(money(169700), _EXPORT)
    assert b.taxable == Decimal(169700)
    assert (b.cgst, b.sgst, b.igst, b.rounding_adjustment) == (
        Decimal(0), Decimal(0), Decimal(0), Decimal(0),
    )
    assert b.total == Decimal(169700)
