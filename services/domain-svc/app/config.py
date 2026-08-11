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

    # --- seller GST identity (from Sample_invoice.pdf; drives place-of-supply) ---
    rv_gstin: str = "05AANCR1978G1Z1"
    rv_pan: str = "AANCR1978G"
    rv_gst_state_code: str = "05"  # Uttarakhand
    rv_gst_state_name: str = "Uttarakhand"

    # --- invoicing (Phase 4). Numbers are <prefix>/<FY>/<gapless serial>. ---
    rv_invoice_prefix: str = "RV"
    rv_seller_address: str = ""  # registered address, printed on the invoice
    rv_seller_bank_details: str = ""  # bank name / A/C / IFSC for payment

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

    # --- auth stub (below-ops role default until a user logs in; D-0002) ---
    rv_current_role: Role = "owner"

    # --- self-hosted auth (D-0014). Set RV_AUTH_SECRET in .env for production. ---
    rv_auth_secret: str = "dev-insecure-secret-change-me-in-.env"
    rv_auth_token_ttl_hours: int = 12
    rv_owner_email: str = "owner@rootsvida.local"
    rv_owner_password: str = "change_me_owner"  # dev seed only; rotate in real use

    # --- LLM (Phase 5). Dormant until RV_ENABLE_LLM=true AND a key is set; until
    # then the factory returns a deterministic stub provider (no network, no spend). ---
    rv_enable_llm: bool = False
    rv_llm_provider: Literal["stub", "gemini", "anthropic"] = "stub"
    gemini_api_key: str = ""
    rv_gemini_model: str = "gemini-flash-latest"  # always-current alias; override in env
    anthropic_api_key: str = ""  # reserved; owner may switch from Gemini later

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
