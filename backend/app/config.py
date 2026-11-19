"""All settings come from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://jobfit:jobfit@localhost:5432/jobfit"

    # LLM: any OpenAI-compatible API. Groq by default.
    # Leave LLM_API_KEY empty to run in "demo mode" (rule-based, no AI calls).
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"

    # Embeddings: "fastembed" runs a small model locally (free, no key).
    # "hash" is a tiny offline fallback used in tests.
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    chunk_size: int = 600
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def demo_mode(self) -> bool:
        return not self.llm_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
