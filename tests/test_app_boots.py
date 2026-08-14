"""Smoke test: the FastAPI app imports and its routers register — no DB required.

Importing `app.main` builds the app and imports every router module. Route decorators
run at import time, which is exactly where a missing *runtime* dependency blows up on
deploy (e.g. python-multipart, needed by the bulk-import upload route, raised
RuntimeError here on boot). Lint/type/most unit tests never import the app, so this
cheap guard catches "it won't even start" in CI instead of on Render.
"""

from __future__ import annotations


def test_app_imports_cleanly() -> None:
    # The import itself is the assertion: a missing dep or a malformed route raises.
    import app.main  # noqa: F401


def test_upload_route_registered() -> None:
    # The file-upload route exists → python-multipart imported cleanly (its absence
    # made the @router.post("/import") decorator raise at module load on deploy).
    from app.api.v1.suppliers import router

    paths = {getattr(route, "path", "") for route in router.routes}
    assert "/suppliers/import" in paths
