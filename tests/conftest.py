"""Shared pytest fixtures and import-path setup.

Puts the domain service and ingestion packages on sys.path so tests can import
them without an install step (mirrors how Alembic's env.py resolves the app).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SVC_DIR = REPO_ROOT / "services" / "domain-svc"

for p in (str(SVC_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
