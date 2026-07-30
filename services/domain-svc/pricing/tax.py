"""Tax split + the `gross_nearest_100` rounding mode (Part 2 §5, plan §1.4).

Indian tour packages (HSN 998555) are invoiced to a **round gross** figure, with
the taxable value *backed out* of it and the tiny residual booked to a rounding
line — reverse-engineered from invoice REPL/2627/TP10:

    gross (nearest ₹100)  169,700.00
    taxable = gross / 1.05           → 161,619.05
    CGST 2.5% = taxable × 0.025      → 4,040.48
    SGST 2.5%                        → 4,040.48
    subtotal                          169,700.01
    rounding adjustment               (−) 0.01
    total                             169,700.00

The place-of-supply outcome (CGST+SGST vs IGST vs export) is decided upstream and
arrives on the `TaxRule`; this module only does the arithmetic for the given
treatment.
"""

from __future__ import annotations

from pricing.model import TaxBreakdown, TaxRule, TaxTreatment
from pricing.money import Money, money, quantize, round_to_nearest

_HUNDRED = money(100)
_ZERO = money(0)


def split_tax(gross_target: Money, tax_rule: TaxRule, step: Money = _HUNDRED) -> TaxBreakdown:
    """Round `gross_target` to the nearest `step`, back out the taxable value and
    the tax halves (each at 2dp), and book the residual to the rounding line."""
    gross = round_to_nearest(gross_target, step)

    if tax_rule.treatment is TaxTreatment.EXPORT or tax_rule.rate == _ZERO:
        # Zero-rated: the gross is the taxable value, no GST, no residual.
        return TaxBreakdown(gross, _ZERO, _ZERO, _ZERO, _ZERO, gross)

    taxable = quantize(gross / (money(1) + tax_rule.rate))
    cgst = sgst = igst = _ZERO
    if tax_rule.treatment is TaxTreatment.CGST_SGST:
        half = quantize(taxable * (tax_rule.rate / money(2)))
        cgst = sgst = half
    else:  # IGST — single inter-state levy
        igst = quantize(taxable * tax_rule.rate)

    subtotal = taxable + cgst + sgst + igst
    rounding_adjustment = gross - subtotal
    return TaxBreakdown(taxable, cgst, sgst, igst, rounding_adjustment, gross)
