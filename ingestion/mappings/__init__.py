"""Per-sheet ingestion mappings.

A `SheetSpec` declares *how* a given source sheet is read into staging: which
workbook it lives in, where its header row sits, and which parser tier it belongs
to (mechanical / assisted / bespoke / manual — plan §1.2). The staging framework
(Milestone 5) uses only `workbook`, `header_row`, `first_data_row` and
`parser_strategy`; the field-level column→canonical mapping is added per sheet as
each is migrated (Milestone 6 onward).
"""

from ingestion.mappings.registry import SheetSpec, resolve_spec

__all__ = ["SheetSpec", "resolve_spec"]
