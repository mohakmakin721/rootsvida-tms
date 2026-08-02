"""API v1 router aggregator.

Sub-routers are registered here as milestones land — never wired ad hoc in
main.py. Milestone 8 mounts the review queue.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    clients,
    destinations,
    invoices,
    itineraries,
    markup_rules,
    pricing,
    projects,
    quotes,
    review,
    roles,
    suppliers,
)

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/ping", tags=["meta"])
def ping() -> dict[str, str]:
    """Cheap liveness ping for the API surface."""
    return {"status": "ok", "api": "v1"}


api_router.include_router(auth.router)
api_router.include_router(roles.router)
api_router.include_router(review.router)
api_router.include_router(suppliers.router)
api_router.include_router(destinations.router)
api_router.include_router(markup_rules.router)
api_router.include_router(clients.router)
api_router.include_router(projects.router)
api_router.include_router(itineraries.router)
api_router.include_router(quotes.router)
api_router.include_router(invoices.router)
api_router.include_router(pricing.router)
