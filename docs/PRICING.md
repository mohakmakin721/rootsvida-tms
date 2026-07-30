# Pricing engine

`services/domain-svc/pricing/` — a **pure** library (Part 2 §5). No database, no
network, no clock, no LLM: frozen dataclasses in, a `PricedQuote` out. Determinism
owns money (D-0001). Every quote records the `engine_version` that produced it, so
an old quote always explains itself.

## The two rules that matter

- **`Decimal`, never `float`.** `money()` rejects floats so binary rounding error
  can never enter a calculation.
- **Round once, ROUND_HALF_UP.** Costs stay exact all the way through; rounding
  happens only at the policy boundary (matching Excel/Tally). This is what stops a
  ₹0.01 drift becoming a ₹40 discrepancy on a group.

## The algorithm

```
per segment s:
  accommodation(s) = Σ over stays s is present in:
                       room_rate[occupancy(s)] × nights ÷ occupancy_divisor(s)
  shared(s)        = Σ over SHARED components applying to s: amount ÷ Σ pax-in-bucket
  direct(s)        = Σ over DIRECT components applying to s: amount   (already per-pax)
  base_cost(s)     = accommodation + shared + direct
  sell(s)          = round( markup(base_cost(s)) × (1 + gst) )     [NEAREST_1]
group_total  = Σ sell(s) × pax(s)
revenue_ex_tax = Σ markup(base_cost(s)) × pax(s)         # true revenue, ex-GST
margin_pct   = (revenue_ex_tax − total_cost) / revenue_ex_tax
```

Modules: `money` (primitives) · `model` (inputs/outputs) · `engine` (cost + sell)
· `tax` (place-of-supply split + gross_nearest_100).

## Decisions baked in

| Concern | Rule |
|---|---|
| Markup vs margin | Explicit `MarkupBasis` enum: `markup_on_cost` (×(1+m)) vs `margin_on_sell` (÷(1−m)). Never ambiguous. |
| GST is a cost | HSN 998555 is taxed **without ITC**, so GST is a real cost. `margin_pct` is computed on **ex-tax** revenue, so tax never inflates margin. |
| Place of supply | Resolved from seller (Uttarakhand 05) vs buyer state/country against the DB `tax_rules` (D-0013): intra→CGST+SGST, inter→IGST, international→CGST+SGST. Overridable. |
| Rounding | `NEAREST_1` — round each per-pax sell to the rupee. `GROSS_NEAREST_100` — price to a round ₹100 gross, back out the taxable value into a `TaxBreakdown`, book the residual to a rounding line (invoice mode). |
| Guardrail | `MarginBelowFloor` raised when `margin_pct < margin_floor`; blocks issuance unless a `MarginOverride` (mandatory reason; Owner-only, enforced by the app) is supplied. |
| Traceability | Every `SegmentPrice` carries a `trace` whose amounts sum exactly to `sell_per_pax`. |

## Using it (from the app)

```python
from pricing.engine import price
from pricing.model import PricingInput  # build from resolved rates/segments
from app.services.tax import resolve_tax_rule, to_pricing_tax_rule

rule = resolve_tax_rule(session, org_id, buyer_state_code="07", buyer_country="IN")
inp = PricingInput(..., tax_rule=to_pricing_tax_rule(rule), ...)
quote = price(inp)                       # or price(inp, margin_override=...)
```

Rates arrive **already resolved** by date/season (the caller does that); the pure
engine just prices what it's given.

## Tests (run in CI, forever)

- `test_golden_jaipur.py` — the full workbook to the rupee (65,597 / 47,303 /
  26,956 / 4,03,327 / profit 67,277 / USD 4,245.55).
- `test_golden_invoice_tp10.py` — invoice split (1,61,619.05 / 4,040.48 /
  4,040.48 / −0.01 / 1,69,700.00).
- `test_pricing_properties.py` — Hypothesis: segments reconcile to the group,
  margins never negative, pricing is deterministic, no drift over long itineraries.
- `test_pricing_snapshot.py` — pins the headline output of a representative quote.

See [DECISIONS.md](DECISIONS.md) for the *why*.
