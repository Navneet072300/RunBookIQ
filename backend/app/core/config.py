from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    log_level: str = "INFO"
    default_tenant_id: str = "default"

    # Database
    database_url: str = "postgresql+asyncpg://runbookiq:runbookiq@localhost:5432/runbookiq"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Gemini (LLM + embeddings via OpenAI-compatible API)
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_model: str = "gemini-2.0-flash"
    llm_max_tokens: int = 4096

    # Embeddings
    embedding_model: str = "text-embedding-004"
    embedding_batch_size: int = 100
    embedding_dimensions: int = 768  # text-embedding-004 outputs 768 dims

    # Slack
    slack_webhook_url: Optional[str] = None

    # Zabbix
    zabbix_api_url: Optional[str] = None
    zabbix_user: Optional[str] = None
    zabbix_password: Optional[str] = None

    # Kubernetes
    k8s_kubeconfig: Optional[str] = None
    k8s_namespace: str = "default"

    # Prometheus
    prometheus_alertmanager_url: Optional[str] = None

    # Uploads
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50

    # RAG
    rag_top_k: int = 5
    dedup_ttl_seconds: int = 300  # 5 min

    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if "postgresql://" in v and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
