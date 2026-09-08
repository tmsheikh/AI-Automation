"""Central configuration loaded from environment / .env.

Nothing secret is hard-coded; everything comes from the environment. See
`.env.example` for the full list and `docs/01-instagram-business-account-setup.md`
for where each Meta value comes from.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic / Claude
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5"

    # Meta / Instagram
    webhook_verify_token: str = "change-me"
    meta_app_secret: str = ""
    instagram_access_token: str = ""
    instagram_account_id: str = ""
    graph_api_version: str = "v21.0"

    # Calendly
    calendly_scheduling_url: str = "https://calendly.com/your-handle/consultation"

    # Business
    business_name: str = "Your Jewelry Studio"
    business_currency: str = "USD"

    # App
    database_path: str = "data/agent.db"
    log_level: str = "INFO"

    @property
    def graph_base_url(self) -> str:
        return f"https://graph.instagram.com/{self.graph_api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
