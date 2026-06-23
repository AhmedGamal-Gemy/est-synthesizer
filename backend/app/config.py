"""
EST Synthesizer — Application Configuration
=============================================

All settings are loaded from environment variables (``.env`` file) with
sensible defaults.  Each section is documented below.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ═══════════════════════════════════════════════════════════════════════════
    #  Server
    # ═══════════════════════════════════════════════════════════════════════════
    # Controls where the FastAPI / Uvicorn server binds.
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    LOG_LEVEL: str = "INFO"
    # Log format: "console" for colored human-readable, "json" for structured JSON.
    LOG_FORMAT: str = "console"
    # Enable uvicorn auto-reload (dev convenience; MUST be False in production).
    UVICORN_RELOAD: bool = False

    # ═══════════════════════════════════════════════════════════════════════════
    #  Mistral AI (LLM)
    # ═══════════════════════════════════════════════════════════════════════════
    # Required for all LLM generation calls (Mistral API).
    # Obtain your key at https://console.mistral.ai
    MISTRAL_API_KEY: str
    # Requests per second — avoids hitting Mistral's rate limit.
    MISTRAL_RATE_LIMIT: float = 1.0
    # Optional LiteLLM proxy URL for custom routing / caching.
    LITELLM_PROXY_URL: str = "http://localhost:4000"
    # Master key for LiteLLM proxy auth (required when using the proxy).
    LITELLM_MASTER_KEY: str = ""
    # Model alias used when calling through the proxy (e.g. "mistral-small").
    LITELLM_MODEL: str = ""

    # ═══════════════════════════════════════════════════════════════════════════
    #  Qdrant (Vector Database)
    # ═══════════════════════════════════════════════════════════════════════════
    # Stores passage embeddings for semantic search.  Run via Docker:
    #   docker compose up -d
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_LONG: str = "long_passages"
    QDRANT_COLLECTION_SHORT: str = "short_passages"

    # ═══════════════════════════════════════════════════════════════════════════
    #  Embedding Model
    # ═══════════════════════════════════════════════════════════════════════════
    # Local Sentence-Transformer model for passage / query embeddings.
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_VECTOR_SIZE: int = 1024
    # Instruction prefix prepended to query texts (BGE convention).
    EMBEDDING_QUERY_PREFIX: str = (
        "Represent this sentence for searching relevant passages: "
    )

    # ═══════════════════════════════════════════════════════════════════════════
    #  Local File Paths
    # ═══════════════════════════════════════════════════════════════════════════
    SQLITE_PATH: str = "data/db/est.db"
    GENERATED_PDF_PATH: str = "data/generated/"

    # ═══════════════════════════════════════════════════════════════════════════
    #  Scraper — Project Gutenberg (Gutendex API)
    # ═══════════════════════════════════════════════════════════════════════════
    # Public-domain book catalogue used to source EST reading passages.
    GUTENDEX_BASE_URL: str = "https://gutendex.com/books"
    # Max unique books fetched per `fetch_catalogue()` call.
    GUTENDEX_MAX_BOOKS: int = 200
    # Per-request timeout for Gutendex API calls (catalogue search).
    GUTENDEX_REQUEST_TIMEOUT: float = 15.0
    # Per-book timeout when downloading full passage text.
    GUTENDEX_PASSAGE_TIMEOUT: float = 30.0
    # Books with all authors born before this year are filtered out
    # (pre-1700 English is too archaic for EST).
    GUTENDEX_MIN_AUTHOR_BIRTH_YEAR: int = 1700

    # ═══════════════════════════════════════════════════════════════════════════
    #  LLM Generation Pipeline
    # ═══════════════════════════════════════════════════════════════════════════
    LLM_MODEL: str = "mistral/mistral-small-latest"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 4096
    # Number of times to retry an LLM call on transient failure.
    LLM_MAX_RETRIES: int = 3
    # Seconds to wait between retries.
    LLM_RETRY_DELAY_SECONDS: int = 2

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
