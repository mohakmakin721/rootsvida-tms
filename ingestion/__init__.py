"""RootsVida TMS ingestion package.

Tiered ingestion of legacy workbooks into staging → candidates → review queue.
Milestone 1 provides only the CLI shell; the mechanical/assisted/bespoke loaders
land in Milestone 5. Nothing here writes directly to canonical tables.
"""

__version__ = "0.1.0"
