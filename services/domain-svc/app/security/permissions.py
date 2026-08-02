"""The permission catalog — the fixed vocabulary of capabilities the app checks.

Roles are dynamic (owner-managed, DB-backed); *permissions* are not. A permission
exists only if the code enforces it somewhere via `require_permission(...)`, so the
catalog here is the single source of truth: the roles UI offers exactly these
toggles, and every gated endpoint references one of these keys. Adding a genuinely
new capability means adding a permission here AND a gate that checks it.
"""

from __future__ import annotations

from dataclasses import dataclass

# Permission keys — reference these constants from gates so a typo is a NameError,
# not a silent 403 that never fires.
USERS_MANAGE = "users.manage"
SUPPLIERS_MANAGE = "suppliers.manage"
MARKUP_MANAGE = "markup.manage"
QUOTES_ISSUE = "quotes.issue"
COSTING_VIEW = "costing.view"
INVOICES_MANAGE = "invoices.manage"


@dataclass(frozen=True)
class Permission:
    key: str
    label: str
    description: str
    group: str


PERMISSIONS: tuple[Permission, ...] = (
    Permission(
        USERS_MANAGE, "Manage users & roles",
        "Add, edit and remove users; create roles and set their permissions.",
        "Administration",
    ),
    Permission(
        SUPPLIERS_MANAGE, "Manage suppliers & rates",
        "Create and edit suppliers, rates, room types, contacts and destinations.",
        "Supplier book",
    ),
    Permission(
        MARKUP_MANAGE, "Manage markup rules",
        "Create and edit the markup / margin rules pricing uses.",
        "Pricing",
    ),
    Permission(
        QUOTES_ISSUE, "Issue quotes",
        "Freeze a draft quote into an issued, immutable version.",
        "Pricing",
    ),
    Permission(
        COSTING_VIEW, "View internal costing",
        "Download the confidential internal costing workbook (shows margin).",
        "Pricing",
    ),
    Permission(
        INVOICES_MANAGE, "Manage invoices",
        "Generate GST invoices and credit notes.",
        "Billing",
    ),
)

ALL_PERMISSION_KEYS: frozenset[str] = frozenset(p.key for p in PERMISSIONS)
