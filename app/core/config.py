import secrets
from functools import lru_cache
from typing import List

from pydantic import EmailStr, field_validator, model_validator
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
    allowed_hosts: List[str] = ["localhost", "127.0.0.1"]
    max_request_body_bytes: int = 120 * 1024 * 1024
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120
    auth_rate_limit_per_minute: int = 10

    # --- database ---
    # Production: postgresql+psycopg2://user:pass@host:5432/dbname
    # PostgreSQL is mandatory for this application.
    database_url: str = "postgresql+psycopg2://app:app@localhost:5432/app"

    # --- auth / jwt ---
    # MUST be overridden in production via env var JWT_SECRET_KEY.
    jwt_secret_key: str = ""
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
    rag_chunk_size: int = 400
    rag_chunk_overlap: int = 60
    # --- OCR for scanned PDFs ---
    ocr_language: str = "en"
    ocr_dpi: int = 180
    ocr_min_native_chars: int = 40
    ocr_min_native_words: int = 8

    @model_validator(mode="before")
    @classmethod
    def _prepare_secret(cls, data):
        data = dict(data or {})
        environment = data.get("environment", "development")
        if environment == "production" and not data.get("jwt_secret_key"):
            raise ValueError("JWT_SECRET_KEY must be explicitly configured in production")
        if environment != "production" and not data.get("jwt_secret_key"):
            data["jwt_secret_key"] = secrets.token_urlsafe(32)
        return data

    @model_validator(mode="after")
    def _validate_production_security(self):
        if self.is_production:
            if not self.jwt_secret_key or self.jwt_secret_key == "change-me-to-a-real-random-secret":
                raise ValueError("JWT_SECRET_KEY must be explicitly configured in production")
            if len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origins are forbidden in production")
            if not self.allowed_hosts:
                raise ValueError("ALLOWED_HOSTS must be configured in production")
            if self.first_admin_password == "ChangeMe123!":
                raise ValueError("FIRST_ADMIN_PASSWORD must be changed before production")
        return self

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
