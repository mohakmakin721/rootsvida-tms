"""Application configuration.

Single source of settings, loaded from environment (and the repo-root `.env`
in local dev). Secrets never live in code — see `.env.example`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is three levels up from this file:
#   <root>/services/domain-svc/app/config.py
REPO_ROOT = Path(__file__).resolve().parents[3]

Role = Literal["owner", "ops_manager", "sales", "accounts", "readonly"]


class Settings(BaseSettings):
    """Runtime configuration. Field names map to env vars (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- organization ---
    rv_org_name: str = "Rootsvida Experiences Private Limited"
    rv_org_slug: str = "rootsvida"

    # --- database ---
    database_url: str = (
        "postgresql+psycopg://rootsvida:change_me_in_local_env"
        "@localhost:5432/rootsvida_tms"
    )
    rv_enable_pgvector: bool = False

    # --- source data ---
    source_data_dir: Path = REPO_ROOT

    # --- service ---
    app_env: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"
    domain_svc_host: str = "0.0.0.0"
    domain_svc_port: int = 8000

    # --- auth stub (Phase 1; real auth in Phase 3 — see docs/DECISIONS.md D-0002) ---
    rv_current_role: Role = "owner"

    # --- LLM (Phase 1: DORMANT — see DECISIONS.md D-0007) ---
    anthropic_api_key: str = ""
    rv_enable_llm: bool = False

    # --- roles permitted to see commercial (commission/margin) data ---
    commercial_roles: tuple[Role, ...] = Field(
        default=("owner", "ops_manager"), exclude=True
    )

    def can_view_commercials(self, role: Role | None = None) -> bool:
        """Whether the given role (default: current) may read commission/margin."""
        return (role or self.rv_current_role) in self.commercial_roles


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
