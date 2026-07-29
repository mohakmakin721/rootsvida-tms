"""API v1 router aggregator.

Sub-routers are registered here as milestones land — never wired ad hoc in
main.py. Milestone 8 mounts the review queue.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import review

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/ping", tags=["meta"])
def ping() -> dict[str, str]:
    """Cheap liveness ping for the API surface."""
    return {"status": "ok", "api": "v1"}


api_router.include_router(review.router)
