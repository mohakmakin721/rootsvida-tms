"""API v1 router aggregator.

Phase 1 mounts the review-queue endpoints (Milestone 8). For now it exposes a
version ping so the frontend contract and OpenAPI generation have a stable base.
Sub-routers are added here as milestones land — never wired ad hoc in main.py.
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/ping", tags=["meta"])
def ping() -> dict[str, str]:
    """Cheap liveness ping for the API surface."""
    return {"status": "ok", "api": "v1"}


# Milestone 8 will register:  api_router.include_router(review.router)
