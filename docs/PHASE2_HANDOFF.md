# Phase 2 — handoff summary

**Status: complete** (9/9 milestones). Phase 2 is the **deterministic pricing
engine** — the financial core that turns costs into quotes and invoices. It is a
pure library (`services/domain-svc/pricing/`): no database, no network, no clock,
no LLM. Determinism owns money (D-0001).

## What it does

Given traveller segments, an itinerary, shared costs, markup, tax and FX, it
produces a `PricedQuote` with per-segment cost → sell, group total, **true
margin**, and a full audit trace — then splits GST for the invoice.

```
base_cost(s) = accommodation (occupancy split + presence) + shared (÷ bucket pax) + direct
sell(s)      = round( markup(base_cost) × (1 + gst) )          [round once, ROUND_HALF_UP]
margin_pct   = (revenue_ex_tax − cost) / revenue_ex_tax        [GST is a cost, not margin]
```

## Proven to the rupee (both run in CI, forever)

- **Jaipur quote** — the full workbook: 65,597 / 47,303 / 26,956 / group 4,03,327
  / profit 67,277 / USD 4,245.55.
- **Invoice TP10** — gross_nearest_100 split: taxable 1,61,619.05 / CGST 4,040.48
  / SGST 4,040.48 / rounding −0.01 / total 1,69,700.00.

Plus Hypothesis property tests (reconciliation, non-negative margin, determinism,
no drift) and a snapshot guard. **136 tests; ruff + mypy green.**

## Layout & entry points

| area | where |
|---|---|
| Money primitives | `pricing/money.py` (Decimal, ROUND_HALF_UP; rejects float) |
| Inputs/outputs | `pricing/model.py` (PricingInput → PricedQuote, MarkupBasis enum) |
| Cost + sell | `pricing/engine.py` (`price()`, `MarginBelowFloor`) |
| Tax split / invoice | `pricing/tax.py` (`split_tax`, gross_nearest_100) |
| Place-of-supply | `app/services/tax.py` + `tax_rules` table (seeded) |
| Tests | `tests/test_pricing_*.py`, `tests/test_golden_*.py`, `test_place_of_supply.py` |
| Guide | [PRICING.md](PRICING.md) |

## Using it (from the app)

```python
from pricing.engine import price
from app.services.tax import resolve_tax_rule, to_pricing_tax_rule

rule = resolve_tax_rule(session, org_id, buyer_state_code="07", buyer_country="IN")
inp  = PricingInput(..., tax_rule=to_pricing_tax_rule(rule), margin_floor=Decimal("0.10"))
quote = price(inp)                     # raises MarginBelowFloor unless margin_override=...
```

Rates arrive **already resolved** by date/season; the engine prices what it's given.

## Load-bearing decisions (see [DECISIONS.md](DECISIONS.md))

- **D-0001** AI never owns money — determinism owns all arithmetic.
- **D-0007** No LLM in Phase 1/2; the engine is pure Python.
- **D-0012** Free/open-source & self-hostable — the engine has zero paid deps.
- **D-0013** GST place-of-supply (seller Uttarakhand 05): intra→CGST+SGST,
  inter→IGST, international→CGST+SGST; rules stored as data, overridable, CA-confirmable.

## Guarantees worth trusting

- **Exact & round-once:** costs stay exact Decimal; rounding happens once, the
  Excel/Tally way. No float ever enters.
- **True margin:** computed on ex-tax revenue, so non-reclaimable GST (HSN 998555)
  never inflates it.
- **Blocks bad quotes:** below the margin floor, issuance is refused without an
  Owner override + reason.
- **Traceable & versioned:** every number has a trace; every quote records
  `engine_version`.

## Next (Phase 3, not started)

The **web app** — itinerary builder and quote UI (mobile-first) on top of this
engine, wiring resolved rates + segments into `PricingInput`. Then documents /
invoices (Phase 4).

## Reference

[PRICING.md](PRICING.md) · [DATA_DICTIONARY.md](DATA_DICTIONARY.md) ·
[DECISIONS.md](DECISIONS.md) · [PHASE1_HANDOFF.md](PHASE1_HANDOFF.md)
