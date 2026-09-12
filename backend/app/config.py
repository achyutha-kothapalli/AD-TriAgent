from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application configuration. Secrets are loaded only on the server."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cors_origins: str = "http://localhost:5173"
    data_dir: str = "data/generated"
    runtime_dir: str = "data/runtime"
    llm_api_key: str | None = None
    llm_model: str = ""
    llm_base_url: str | None = None
    llm_enabled: bool = True
    slack_webhook_url: str | None = None
    ambiguous_api_base_url: str | None = None
    ambiguous_api_token: str | None = None
    ambiguous_workspace_id: str | None = None
    ambiguous_webhook_secret: str | None = None

    @property
    def scenario_path(self) -> Path:
        return self._path_from_root(self.data_dir)

    @property
    def runtime_path(self) -> Path:
        return self._path_from_root(self.runtime_dir)

    def _path_from_root(self, configured_path: str) -> Path:
        path = Path(configured_path)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
