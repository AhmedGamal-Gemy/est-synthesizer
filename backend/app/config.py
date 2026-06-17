from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ── server ──────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ── external services ───────────────────────────
    MISTRAL_API_KEY: str
    MISTRAL_RATE_LIMIT: float = 1.0

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_LONG: str = "long_passages"
    QDRANT_COLLECTION_SHORT: str = "short_passages"

    # ── paths ───────────────────────────────────────
    SQLITE_PATH: str = "data/db/est.db"
    GENERATED_PDF_PATH: str = "data/generated/"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
