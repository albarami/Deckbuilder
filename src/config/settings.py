"""Pydantic Settings — loads all configuration from .env file."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DeckForge configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    openai_api_key: SecretStr
    anthropic_api_key: SecretStr
    semantic_scholar_api_key: SecretStr = SecretStr("")

    # Model names (overridable per env)
    openai_model_gpt54: str = "gpt-5.4"
    anthropic_model_opus: str = "claude-opus-4-6"
    anthropic_model_sonnet: str = "claude-sonnet-4-6"

    # Azure (optional for local dev)
    azure_search_endpoint: str = ""
    azure_search_key: SecretStr = SecretStr("")
    azure_search_index: str = "deckforge-knowledge"
    azure_openai_endpoint: str = ""
    azure_openai_key: SecretStr = SecretStr("")
    azure_openai_embedding_model: str = "text-embedding-3-large"

    # SharePoint (production only)
    sharepoint_tenant_id: str = ""
    sharepoint_client_id: str = ""
    sharepoint_client_secret: SecretStr = SecretStr("")
    sharepoint_site_url: str = ""

    # Local dev paths + backend selection
    environment: str = "local"
    storage_backend: str = "local"
    search_backend: str = "local"
    state_backend: str = "local"
    local_docs_path: str = "data test"
    template_path: str = "./templates/Presentation6.pptx"
    output_path: str = "./output"
    state_path: str = "./state"
    log_level: str = "DEBUG"

    # Renderer feature flag — "legacy" (default) or "template_v2"
    renderer_mode: str = "legacy"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Call get_settings.cache_clear() in tests."""
    return Settings()  # type: ignore[call-arg]  # API keys provided by .env at runtime
