"""Mechanical normalisation of staged rows into canonical supplier candidates.

Tier A of the plan (§1.2): a per-sheet column mapping plus shared helpers, no
LLM (D-0007). This module is pure — it turns a `{column: raw_value}` dict into a
`NormalizedSupplier` (or `None` when the row has no usable identity) without
touching the database. Prices are deliberately NOT parsed into rates: the rough
"Price Range" text stays in staging as raw provenance (D-0007). What comes out
here is an *unverified prospect*, never a verified rate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.enums import SupplierKind

# Remarks/status phrases that mean "this contact can't be used as-is".
_UNUSABLE = re.compile(r"no reply|via website|via mail|find the owner|not reach", re.IGNORECASE)


def _text(value: Any) -> str | None:
    """Trimmed string form of a cell, or None if empty. Integral floats lose their
    trailing `.0` (Excel stores plain numbers as floats)."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = str(value).strip()
    return s or None


def normalize_phone(value: Any) -> tuple[str | None, str | None]:
    """Best-effort (phone_raw, phone_e164) for an Indian contact cell.

    `phone_raw` always preserves the source verbatim (never dropped — plan §1.1.3).
    `phone_e164` is set only when the digits confidently form an Indian number;
    otherwise it stays None (a landline or malformed value is kept raw, not guessed).
    """
    raw = _text(value)
    if raw is None:
        return None, None
    digits = re.sub(r"\D", "", raw)
    e164: str | None = None
    if len(digits) == 10 and digits[0] in "6789":
        e164 = f"+91{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        e164 = f"+{digits}"
    elif len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        e164 = f"+91{digits[1:]}"
    return raw, e164


@dataclass(frozen=True)
class NormalizedContact:
    phone_raw: str | None = None
    phone_e164: str | None = None
    email: str | None = None
    website: str | None = None
    unusable_reason: str | None = None

    @property
    def is_empty(self) -> bool:
        return not any((self.phone_raw, self.email, self.website))


@dataclass(frozen=True)
class NormalizedSupplier:
    kind: SupplierKind
    display_name: str
    category: str | None = None
    property_type: str | None = None
    destination_name: str | None = None
    destination_state: str | None = None
    status: str = "prospect"
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    contact: NormalizedContact | None = None

    @property
    def has_destination(self) -> bool:
        return self.destination_name is not None


def normalize_rajasthan(raw: dict[str, Any]) -> NormalizedSupplier | None:
    """Map one Rajasthan-sheet row to a supplier candidate.

    Returns None when the row carries no usable name — an anonymous prospect the
    normaliser refuses to invent an identity for (the caller flags it for review).
    """
    name = _text(raw.get("Name"))
    if name is None:
        return None

    property_type = _text(raw.get("Type"))
    # All accommodation is a 'stay' vendor now; the homestay/hotel nuance is kept
    # as property_type rather than a distinct kind.
    kind = SupplierKind.STAY

    remarks = _text(raw.get("Remarks"))
    status_note = _text(raw.get("Status"))
    phone_raw, phone_e164 = normalize_phone(raw.get("Contact"))
    reason_source = " ".join(filter(None, (remarks, status_note)))
    unusable = reason_source if reason_source and _UNUSABLE.search(reason_source) else None

    contact = NormalizedContact(
        phone_raw=phone_raw,
        phone_e164=phone_e164,
        email=_text(raw.get("Email id")),
        website=_text(raw.get("Website")),
        unusable_reason=unusable if phone_e164 is None else None,
    )

    features = _text(raw.get("Extra features"))
    return NormalizedSupplier(
        kind=kind,
        display_name=name,
        category=_text(raw.get("Category")),
        property_type=property_type,
        destination_name=_text(raw.get("Place")),
        destination_state="Rajasthan",
        notes=remarks,
        tags=[features] if features else [],
        contact=None if contact.is_empty else contact,
    )


# Sheet name -> normaliser. Only sheets with a written mapping can be migrated;
# everything else raises in the migrate step (no silent guessing).
NORMALIZERS = {
    "Rajasthan": normalize_rajasthan,
}
