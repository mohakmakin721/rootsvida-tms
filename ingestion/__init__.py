"""RootsVida TMS ingestion package.

Tiered ingestion of legacy workbooks into staging → candidates → review queue.
Milestone 5 provides the staging framework: `stage_sheet` fingerprints a source
workbook into `source_documents` and upserts its rows verbatim into
`raw_import_rows`, idempotently. Normalisation into canonical tables and the
review queue are downstream (Milestone 6+). Nothing here writes canonical rates.
"""

__version__ = "0.1.0"
