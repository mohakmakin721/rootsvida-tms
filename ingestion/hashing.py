"""Content fingerprints for provenance and idempotency.

Two hashes underpin the whole reingest story (plan §29):

  - `sha256_file` fingerprints a *source file* so re-ingesting identical bytes
    resolves to the same `source_documents` row instead of duplicating it.
  - `content_fingerprint` fingerprints a *single staged row's* raw values so a
    re-run can tell an unchanged row (skip) from a changed one (update).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str | Path) -> str:
    """Streaming SHA-256 of a file's bytes, hex-encoded."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_fingerprint(values: dict[str, Any]) -> str:
    """Stable SHA-256 over a row's raw values.

    Canonical JSON (sorted keys, no whitespace) so the same content always hashes
    to the same digest regardless of key order; `default=str` keeps it total for
    any stray non-JSON value that slipped through coercion.
    """
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
