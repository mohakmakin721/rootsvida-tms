# ---------------------------------------------------------------------------
# RootsVida TMS — backend (FastAPI domain service) production image.
#
# Build context is the REPO ROOT (the code expects the repo layout: the app
# lives in services/domain-svc, migrations in db/, the seed in scripts/).
#
#   docker build -t rootsvida-api .
#   docker run -p 8000:8000 --env-file .env rootsvida-api
#
# On Render (free web service, Docker runtime) this is built and run for you;
# Render injects $PORT, which the CMD binds. See docs/DEPLOYMENT.md.
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/services/domain-svc

WORKDIR /app

# Install the domain service (pulls runtime deps from its pyproject). Editable
# so `app`/`pricing` import from the source tree and REPO_ROOT resolves to /app
# (parents[3] of app/config.py), matching local behaviour.
COPY services/domain-svc services/domain-svc
# Include the [llm] extra (google-genai) so Gemini works once RV_ENABLE_LLM +
# GEMINI_API_KEY are set; it stays dormant (stub provider) until then.
RUN pip install -e "./services/domain-svc[llm]"

# Migrations + seed live at the repo root layout the code imports expect.
COPY db db
COPY scripts scripts

EXPOSE 8000

# On boot: apply migrations (no-op when already at head) -> seed org + GST rules
# + owner login (idempotent) -> serve. Render provides $PORT; default 8000.
CMD ["sh", "-c", "cd /app/db && python -m alembic upgrade head && cd /app && python scripts/seed_org.py && cd /app/services/domain-svc && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
