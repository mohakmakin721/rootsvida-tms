"""FastAPI application entrypoint for the RootsVida TMS domain service.

Phase 1 scope: health/readiness, API v1 base, OpenAPI. The pricing engine,
document rendering and agent graphs are intentionally NOT here yet (Part 1 §36).
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import text

from app import __version__
from app.api.v1.router import api_router
from app.config import get_settings
from app.db import get_engine

app = FastAPI(
    title="RootsVida TMS — Domain Service",
    version=__version__,
    description=(
        "Canonical data, provenance, and human-review foundation for the "
        "RootsVida Travel Management System. Phase 1."
    ),
)
app.include_router(api_router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness: the process is up. Does not touch the database."""
    settings = get_settings()
    return {"status": "ok", "env": settings.app_env, "version": __version__}


@app.get("/ready", tags=["meta"])
def ready() -> dict[str, str]:
    """Readiness: the process can reach Postgres. Used by orchestration."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "reachable"}
    except Exception as exc:  # noqa: BLE001 — report, don't crash the probe
        return {"status": "degraded", "database": f"unreachable: {type(exc).__name__}"}
