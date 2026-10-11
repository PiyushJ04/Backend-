import secrets
from functools import lru_cache
from typing import List

from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    The ONE place backend config lives. Every other module imports
    `settings` from here - never re-declare a second config/settings
    module elsewhere.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- app ---
    app_name: str = "app"
    environment: str = "development"  # development | staging | production
    api_v1_prefix: str = "/api/v1"
    cors_origins: List[str] = ["http://localhost:5173"]

    # --- database ---
    # Production: postgresql+psycopg2://user:pass@host:5432/dbname
    # PostgreSQL is mandatory for this application.
    database_url: str = "postgresql+psycopg2://app:app@localhost:5432/app"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg2://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg2://", 1)
        return value

    # --- auth / jwt ---
    # MUST be overridden in production via env var JWT_SECRET_KEY.
    jwt_secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- first-run bootstrap admin (central body) ---
    # Used only by scripts/seed_admin.py to create the very first admin.
    first_admin_username: str = "admin"
    first_admin_email: EmailStr = "admin@example.com"
    first_admin_password: str = "ChangeMe123!"

    # --- temp password policy for admin-created users ---
    temp_password_length: int = 12

    # --- email / smtp (for sending first-time credentials) ---
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: EmailStr = "no-reply@example.com"
    smtp_from_name: str = "Admin Team"

    # --- celery / redis (async email pipeline) ---
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- frontend (for links inside emails) ---
    frontend_base_url: str = "http://localhost:5173"

    # --- Phase 5: Hugging Face LLM ---
    # Keep the provider/model configurable so the project is not locked to one model.
    hf_token: str = ""
    hf_provider: str = "auto"
    llm_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    llm_timeout_seconds: float = 60.0

    # --- Phase 5B: embeddings / RAG ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    embedding_timeout_seconds: float = 60.0
    rag_top_k: int = 5
    rag_min_similarity: float = 0.15
    # --- OCR for scanned PDFs ---
    ocr_language: str = "en"
    ocr_dpi: int = 180
    ocr_min_native_chars: int = 40
    ocr_min_native_words: int = 8

    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
