"""Unit tests for backend.app.config — Settings validation, defaults, and overrides."""

import os
from pathlib import Path

import pytest
from pydantic_core._pydantic_core import ValidationError

from backend.app.config import Settings


# ── helper ──────────────────────────────────────────────────────


def _make_settings(**env_overrides):
    """Create Settings with a clean env + specific overrides."""
    # Build a fresh .env in a temp dir so Settings doesn't pick up the real one
    env_file = Path(os.devnull)
    with pytest.MonkeyPatch.context() as mp:
        # Clear all EST-related env vars
        for key in list(os.environ.keys()):
            if key.startswith((
                "MISTRAL_", "QDRANT_", "SQLITE_", "EMBEDDING_",
                "HOST", "PORT", "GENERATED_PDF_PATH",
            )):
                mp.delenv(key, raising=False)
        # Set required key + any overrides
        mp.setenv("MISTRAL_API_KEY", env_overrides.pop("MISTRAL_API_KEY", "test-key"))
        for k, v in env_overrides.items():
            mp.setenv(k, str(v))
        # Point to empty env file so real .env doesn't interfere
        return Settings(_env_file=str(env_file))


# ── Default values ──────────────────────────────────────────────


class TestSettingsDefaults:
    def test_default_host(self):
        s = _make_settings()
        assert s.HOST == "127.0.0.1"

    def test_default_port(self):
        s = _make_settings()
        assert s.PORT == 8000

    def test_default_qdrant_url(self):
        s = _make_settings()
        assert s.QDRANT_URL == "http://localhost:6333"

    def test_default_sqlite_path(self):
        s = _make_settings()
        assert s.SQLITE_PATH == "data/db/est.db"

    def test_default_mistral_rate_limit(self):
        s = _make_settings()
        assert s.MISTRAL_RATE_LIMIT == 1.0

    def test_default_embedding_model(self):
        s = _make_settings()
        assert s.EMBEDDING_MODEL == "BAAI/bge-large-en-v1.5"

    def test_default_embedding_vector_size(self):
        s = _make_settings()
        assert s.EMBEDDING_VECTOR_SIZE == 1024

    def test_default_embedding_query_prefix(self):
        s = _make_settings()
        assert s.EMBEDDING_QUERY_PREFIX == "Represent this sentence for searching relevant passages: "

    def test_default_embedding_query_prefix(self):
        s = _make_settings()
        assert s.EMBEDDING_QUERY_PREFIX == "Represent this sentence for searching relevant passages: "

    def test_default_qdrant_collection_long(self):
        s = _make_settings()
        assert s.QDRANT_COLLECTION_LONG == "long_passages"

    def test_default_qdrant_collection_short(self):
        s = _make_settings()
        assert s.QDRANT_COLLECTION_SHORT == "short_passages"

    def test_default_generated_pdf_path(self):
        s = _make_settings()
        assert s.GENERATED_PDF_PATH == "data/generated/"


# ── MISTRAL_API_KEY is required ────────────────────────────────


class TestMistralApiKeyRequired:
    def test_missing_api_key_raises_validation_error(self):
        with pytest.MonkeyPatch.context() as mp:
            for key in list(os.environ.keys()):
                if key.startswith("MISTRAL_"):
                    mp.delenv(key, raising=False)
            with pytest.raises(ValidationError):
                Settings(_env_file=str(Path(os.devnull)))

    def test_api_key_accepted(self):
        s = _make_settings(MISTRAL_API_KEY="sk-test-123")
        assert s.MISTRAL_API_KEY == "sk-test-123"


# ── .env file override ─────────────────────────────────────────


class TestDotenvOverride:
    def test_dotenv_overrides_host_and_port(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "MISTRAL_API_KEY=dotenv-key\n"
            "HOST=0.0.0.0\n"
            "PORT=9999\n"
        )
        with pytest.MonkeyPatch.context() as mp:
            for key in list(os.environ.keys()):
                if key.startswith(("MISTRAL_", "HOST", "PORT", "QDRANT_")):
                    mp.delenv(key, raising=False)
            s = Settings(_env_file=str(env_file))
            assert s.HOST == "0.0.0.0"
            assert s.PORT == 9999
            assert s.MISTRAL_API_KEY == "dotenv-key"

    def test_dotenv_overrides_qdrant_url(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "MISTRAL_API_KEY=key\n"
            "QDRANT_URL=http://qdrant-test:6333\n"
        )
        with pytest.MonkeyPatch.context() as mp:
            for key in list(os.environ.keys()):
                if key.startswith(("MISTRAL_", "QDRANT_")):
                    mp.delenv(key, raising=False)
            s = Settings(_env_file=str(env_file))
            assert s.QDRANT_URL == "http://qdrant-test:6333"


# ── Env-var override ───────────────────────────────────────────


class TestEnvVarOverride:
    def test_override_host(self):
        s = _make_settings(HOST="0.0.0.0")
        assert s.HOST == "0.0.0.0"

    def test_override_port(self):
        s = _make_settings(PORT=9999)
        assert s.PORT == 9999

    def test_override_qdrant_url(self):
        s = _make_settings(QDRANT_URL="http://custom:6334")
        assert s.QDRANT_URL == "http://custom:6334"

    def test_override_sqlite_path(self):
        s = _make_settings(SQLITE_PATH="/tmp/test.db")
        assert s.SQLITE_PATH == "/tmp/test.db"

    def test_override_mistral_rate_limit(self):
        s = _make_settings(MISTRAL_RATE_LIMIT=2.5)
        assert s.MISTRAL_RATE_LIMIT == 2.5


# ── Validation errors ──────────────────────────────────────────


class TestSettingsValidation:
    def test_invalid_port_type_raises(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("MISTRAL_API_KEY", "test-key")
            mp.setenv("PORT", "not_a_number")
            with pytest.raises(ValidationError):
                Settings(_env_file=str(Path(os.devnull)))

    def test_empty_api_key_accepted(self):
        s = _make_settings(MISTRAL_API_KEY="")
        assert s.MISTRAL_API_KEY == ""


# ── Singleton instance ─────────────────────────────────────────


class TestSettingsSingleton:
    def test_settings_is_settings_instance(self):
        from backend.app.config import settings
        assert isinstance(settings, Settings)

    def test_settings_has_api_key(self):
        from backend.app.config import settings
        assert hasattr(settings, "MISTRAL_API_KEY")
