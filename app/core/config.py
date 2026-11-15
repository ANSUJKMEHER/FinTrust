import os
from typing import List, Optional
from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FinTrust RAG"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "fintrust_user"
    POSTGRES_PASSWORD: str = "fintrust_secure_password"
    POSTGRES_DB: str = "fintrust_db"
    DATABASE_URL: Optional[str] = None

    @computed_field
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            # If standard postgresql:// prefix was given, map to postgresql+psycopg2://
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Security & Cryptography
    JWT_SECRET_KEY: str = "insecure_dev_secret_key_change_in_production_min_32_characters"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Argon2id Parameters (RFC 9106 recommended minimums for sensitive systems)
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST_KIB: int = 65536  # 64 MiB
    ARGON2_PARALLELISM: int = 4

    # Security Features
    AUDIT_LOG_ENABLED: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Ingestion & Storage Settings
    MAX_UPLOAD_SIZE_BYTES: int = 52428800  # 50 MB
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".docx", ".txt", ".md"]
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "application/octet-stream"  # Used by some browsers for markdown/plain text
    ]
    DOCUMENT_STORAGE_DIR: str = "storage/documents"

    # Chunking & NLP Settings
    CHUNK_TARGET_SIZE_TOKENS: int = 512
    CHUNK_OVERLAP_TOKENS: int = 64

    # Embedding & Vector Search Settings
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384

    # Full-Text & Hybrid Retrieval Settings
    RRF_K_CONSTANT: int = 60
    DENSE_SEARCH_LIMIT: int = 25
    SPARSE_SEARCH_LIMIT: int = 25
    RERANK_TOP_K: int = 5

    # Cross-Encoder Reranking Settings
    RERANKING_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Phase 4: LLM Provider & Generation Settings
    LLM_PROVIDER: str = "mock"  # Default to mock in development/testing; production overrides via env
    LLM_MODEL_NAME: str = "gpt-4o-mini"
    LLM_API_KEY: Optional[str] = None
    LLM_API_BASE: Optional[str] = None
    LLM_TEMPERATURE: float = 0.0  # Zero temperature for deterministic compliance responses
    LLM_MAX_TOKENS: int = 1500
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BACKOFF_FACTOR: float = 1.5

    # Phase 4: Context Construction & Sufficiency Settings
    RAG_MAX_CONTEXT_TOKENS: int = 3000
    RAG_SUFFICIENCY_MIN_SCORE: float = 0.30
    RAG_REFUSAL_MESSAGE: str = "The provided documents do not contain sufficient evidence to answer this question reliably."

    # Production Database Pool Tuning
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Production Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_PER_MINUTE: int = 15
    RATE_LIMIT_RAG_PER_MINUTE: int = 60
    RATE_LIMIT_GENERAL_PER_MINUTE: int = 120

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.ENVIRONMENT.lower() in ("production", "prod"):
            # Enforce JWT Secret Key length and complexity
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("In production, JWT_SECRET_KEY must be at least 32 characters long.")
            insecure_markers = ["insecure", "default", "change_in_production", "dev_secret", "secret123"]
            if any(marker in self.JWT_SECRET_KEY.lower() for marker in insecure_markers):
                raise ValueError("In production, JWT_SECRET_KEY cannot contain default or insecure placeholders.")
            if self.DEBUG:
                raise ValueError("In production, DEBUG must be set to False.")
            if not self.POSTGRES_PASSWORD or len(self.POSTGRES_PASSWORD) < 8:
                raise ValueError("In production, POSTGRES_PASSWORD must be configured and at least 8 characters.")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
