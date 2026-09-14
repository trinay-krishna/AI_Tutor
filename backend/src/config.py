"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o"
    openai_fast_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # --- Auth ---
    session_ttl_days: int = 30
    cookie_secure: bool = False
    cookie_name: str = "ai_tutor_session"

    # --- RAG ---
    rag_min_similarity: float = 0.35
    rag_top_k: int = 8
    rag_max_chunks_per_document: int = 3

    # --- Ingestion ---
    ingestion_max_concurrency: int = 3
    ingestion_timeout_seconds: int = 20
    ingestion_max_body_bytes: int = 5 * 1024 * 1024
    ingestion_min_content_chars: int = 200
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 100

    # --- LangSmith (optional, off by default) ---
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
