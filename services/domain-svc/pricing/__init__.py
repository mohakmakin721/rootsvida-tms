"""RootsVida deterministic pricing engine (Phase 2, Part 2 §5).

A **pure** library: no database, no network, no clock, no LLM. Inputs are frozen
dataclasses; output is a priced quote. Determinism owns money (D-0001) — every
rate, allocation, markup, tax and rounding step is a tested pure function.

The engine is versioned (`ENGINE_VERSION`): every quote records the version that
produced it, so an old quote can always explain itself even after the logic
changes.
"""

from __future__ import annotations

__version__ = "0.1.0"
ENGINE_VERSION = f"pricing@{__version__}"
