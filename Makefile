# ---------------------------------------------------------------------------
# RootsVida TMS — task runner.
# Cross-platform note: targets shell out to Python/uv/npm so they work on
# Windows (Git Bash) and *nix. On Windows without `make`, run the underlying
# commands directly or use scripts/ equivalents.
# ---------------------------------------------------------------------------
.DEFAULT_GOAL := help
PY ?= python
SVC := services/domain-svc

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}'

# --- environment -----------------------------------------------------------
.PHONY: up down logs
up: ## Start local stack (Postgres + MinIO)
	docker compose up -d

down: ## Stop local stack
	docker compose down

logs: ## Tail stack logs
	docker compose logs -f

# --- python service --------------------------------------------------------
.PHONY: install
install: ## Create venv and install domain-svc (editable) + dev deps
	cd $(SVC) && $(PY) -m venv .venv && \
		.venv/Scripts/pip install -e ".[dev]" 2>/dev/null || \
		.venv/bin/pip install -e ".[dev]"

.PHONY: api
api: ## Run the FastAPI domain service
	cd $(SVC) && $(PY) -m uvicorn app.main:app --reload --port 8000

.PHONY: lint typecheck
lint: ## Ruff lint
	cd $(SVC) && $(PY) -m ruff check .
typecheck: ## mypy type check
	cd $(SVC) && $(PY) -m mypy app

.PHONY: test
test: ## Run test suite
	$(PY) -m pytest -q

# --- database --------------------------------------------------------------
.PHONY: migrate downgrade revision sql
migrate: ## Apply all Alembic migrations
	cd db && $(PY) -m alembic upgrade head
downgrade: ## Roll back one migration
	cd db && $(PY) -m alembic downgrade -1
revision: ## New autogenerate revision:  make revision m="message"
	cd db && $(PY) -m alembic revision --autogenerate -m "$(m)"
sql: ## Render migrations as offline SQL (no live DB needed)
	cd db && $(PY) -m alembic upgrade head --sql

# --- ingestion -------------------------------------------------------------
.PHONY: ingest reingest dq
ingest: ## Ingest one sheet:  make ingest sheet=Rajasthan
	$(PY) -m ingestion.cli ingest --sheet "$(sheet)"
reingest: ## Rebuild ALL staging + candidates from source (idempotent)
	$(PY) -m ingestion.cli reingest
dq: ## Print data-quality report for the last run
	$(PY) -m ingestion.cli report

# --- web -------------------------------------------------------------------
.PHONY: web web-install
web-install: ## Install web deps
	cd apps/web && npm install
web: ## Run the Next.js review-queue UI
	cd apps/web && npm run dev
