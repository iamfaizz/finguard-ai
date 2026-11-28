from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config comes from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM (only used to WRITE answers; embeddings are local) ---
    llm_provider: str = "ollama"  # "gemini" | "ollama" (default: local, no key) | "claude"
    gemini_api_key: str = Field(default="", validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"))
    gemini_model: str = "gemini-2.5-flash"  # copy a current model name from Google AI Studio
    anthropic_api_key: str = ""
    llm_model_fast: str = "claude-haiku-5-5"  # routine questions
    llm_model_smart: str = "claude-sonnet-5-5"  # harder questions
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.2:3b"
    temperature: float = 0.1
    max_output_tokens: int = 600
    llm_timeout_s: float = 30.0

    # --- retrieval ---
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_path: str = "/data/chroma"
    chroma_collection: str = "finance_kb"
    kb_dir: str = "knowledge"
    top_k: int = 4
    max_distance: float = 0.65  # cosine distance; tune with the eval set

    # --- backend / auth ---
    backend_url: str = "http://backend:8000"
    # MUST equal the backend's secret. The backend calls it JWT_SECRET_KEY; JWT_SECRET also works.
    jwt_secret: str = Field(validation_alias=AliasChoices("JWT_SECRET_KEY", "JWT_SECRET"))
    jwt_algorithm: str = "HS256"
    cors_origins: str = "http://localhost:5173"

    # --- limits ---
    max_question_chars: int = 500
    rate_limit_per_min: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()