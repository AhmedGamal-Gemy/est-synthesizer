from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ── server ──────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ── external services ───────────────────────────
    MISTRAL_API_KEY: str
    MISTRAL_RATE_LIMIT: float = 1.0
    LITELLM_PROXY_URL: str = "http://localhost:4000"

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_LONG: str = "long_passages"
    QDRANT_COLLECTION_SHORT: str = "short_passages"

    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_VECTOR_SIZE: int = 1024
    EMBEDDING_QUERY_PREFIX: str = "Represent this sentence for searching relevant passages: "

    # ── paths ───────────────────────────────────────
    SQLITE_PATH: str = "data/db/est.db"
    GENERATED_PDF_PATH: str = "data/generated/"

    # ── LLM / generation ────────────────────────────
    LLM_MODEL: str = "mistral/mistral-small-latest"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 4096
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY_SECONDS: int = 2

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
