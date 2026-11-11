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
    rag_enabled: bool = True
    rag_top_k: int = 3
    rag_corpus_path: str = "backend/app/knowledge/documents/manifest.json"
    rag_backend: str = "tfidf"
    rag_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "triage_guidance"
    qdrant_local_path: str = "data/runtime/qdrant"
    mlflow_enabled: bool = False
    mlflow_tracking_uri: str | None = None
    mlflow_experiment: str = "AD-TriAgent"
    mlflow_langchain_autolog: bool = False
    slack_webhook_url: str | None = None

    @property
    def scenario_path(self) -> Path:
        return self._path_from_root(self.data_dir)

    @property
    def runtime_path(self) -> Path:
        return self._path_from_root(self.runtime_dir)

    @property
    def rag_corpus_file(self) -> Path:
        return self._path_from_root(self.rag_corpus_path)

    @property
    def qdrant_local_directory(self) -> Path:
        return self._path_from_root(self.qdrant_local_path)

    @property
    def mlflow_local_database(self) -> Path:
        """SQLite database used by the supported local MLflow tracking store."""

        return self.runtime_path / "mlflow.db"

    @property
    def mlflow_local_tracking_uri(self) -> str:
        return f"sqlite:///{self.mlflow_local_database.as_posix()}"

    def _path_from_root(self, configured_path: str) -> Path:
        path = Path(configured_path)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
