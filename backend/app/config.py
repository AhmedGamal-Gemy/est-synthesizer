from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    MISTRAL_API_KEY: str
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_LONG: str = "long_passages"
    QDRANT_COLLECTION_SHORT: str = "short_passages"
    SQLITE_PATH: str = "data/db/est.db"
    GENERATED_PDF_PATH: str = "data/generated/"
    MISTRAL_RATE_LIMIT: float = 1.0

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
