"""Unit tests for backend.app.schemas.llm — LLMConfig & LiteLLMRequest."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.llm import LLMConfig, LiteLLMRequest


# ── LLMConfig ────────────────────────────────────────────────

def test_llm_config_defaults():
    cfg = LLMConfig(model_name="freetheai-smart")
    assert cfg.model_name == "freetheai-smart"
    assert cfg.proxy_base_url == "http://localhost:4000"
    assert cfg.proxy_api_key == "sk-1234"
    assert cfg.temperature == 0.3
    assert cfg.max_tokens == 4096


def test_llm_config_custom_values():
    cfg = LLMConfig(
        model_name="custom-model",
        proxy_base_url="http://custom:5000",
        proxy_api_key="sk-custom",
        temperature=0.7,
        max_tokens=2048,
    )
    assert cfg.proxy_base_url == "http://custom:5000"
    assert cfg.proxy_api_key == "sk-custom"
    assert cfg.temperature == 0.7
    assert cfg.max_tokens == 2048


def test_llm_config_temperature_valid_boundaries():
    for t in [0.0, 0.3, 1.0, 2.0]:
        cfg = LLMConfig(model_name="m", temperature=t)
        assert cfg.temperature == t


def test_llm_config_temperature_negative_invalid():
    with pytest.raises(ValidationError):
        LLMConfig(model_name="m", temperature=-0.1)


def test_llm_config_temperature_above_2_invalid():
    with pytest.raises(ValidationError):
        LLMConfig(model_name="m", temperature=2.1)


def test_llm_config_max_tokens_ge1_valid():
    cfg = LLMConfig(model_name="m", max_tokens=1)
    assert cfg.max_tokens == 1


def test_llm_config_max_tokens_zero_invalid():
    with pytest.raises(ValidationError):
        LLMConfig(model_name="m", max_tokens=0)


def test_llm_config_max_tokens_negative_invalid():
    with pytest.raises(ValidationError):
        LLMConfig(model_name="m", max_tokens=-1)


def test_llm_config_missing_model_name_invalid():
    with pytest.raises(ValidationError):
        LLMConfig()


def test_llm_config_strict_allows_extra_fields():
    """strict=True enforces strict types but does NOT forbid extra fields."""
    cfg = LLMConfig(model_name="m", extra_field="ignored")
    assert cfg.model_name == "m"


# ── LiteLLMRequest ───────────────────────────────────────────

def test_litellm_request_defaults():
    req = LiteLLMRequest(
        model="freetheai-smart",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert req.model == "freetheai-smart"
    assert req.temperature == 0.3
    assert req.max_tokens == 4096
    assert req.response_format is None


def test_litellm_request_custom_temperature():
    req = LiteLLMRequest(
        model="m",
        messages=[{"role": "user", "content": "Hi"}],
        temperature=1.5,
    )
    assert req.temperature == 1.5


def test_litellm_request_custom_max_tokens():
    req = LiteLLMRequest(
        model="m",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=1024,
    )
    assert req.max_tokens == 1024


def test_litellm_request_messages_min_length_1():
    # Empty messages list should fail
    with pytest.raises(ValidationError):
        LiteLLMRequest(model="m", messages=[])


def test_litellm_request_messages_single_valid():
    req = LiteLLMRequest(
        model="m",
        messages=[{"role": "user", "content": "Test"}],
    )
    assert len(req.messages) == 1


def test_litellm_request_messages_multiple_valid():
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    req = LiteLLMRequest(model="m", messages=msgs)
    assert len(req.messages) == 2


def test_litellm_request_temperature_valid_boundaries():
    for t in [0.0, 1.0, 2.0]:
        req = LiteLLMRequest(
            model="m",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=t,
        )
        assert req.temperature == t


def test_litellm_request_temperature_negative_invalid():
    with pytest.raises(ValidationError):
        LiteLLMRequest(
            model="m",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=-0.1,
        )


def test_litellm_request_temperature_above_2_invalid():
    with pytest.raises(ValidationError):
        LiteLLMRequest(
            model="m",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=2.1,
        )


def test_litellm_request_max_tokens_ge1_valid():
    req = LiteLLMRequest(
        model="m",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=1,
    )
    assert req.max_tokens == 1


def test_litellm_request_max_tokens_zero_invalid():
    with pytest.raises(ValidationError):
        LiteLLMRequest(
            model="m",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=0,
        )


def test_litellm_request_response_format_explicit():
    req = LiteLLMRequest(
        model="m",
        messages=[{"role": "user", "content": "Hi"}],
        response_format={"type": "json_object"},
    )
    assert req.response_format == {"type": "json_object"}


def test_litellm_request_missing_model_invalid():
    with pytest.raises(ValidationError):
        LiteLLMRequest(messages=[{"role": "user", "content": "Hi"}])


def test_litellm_request_missing_messages_invalid():
    with pytest.raises(ValidationError):
        LiteLLMRequest(model="m")


def test_litellm_request_strict_allows_extra_fields():
    """strict=True enforces strict types but does NOT forbid extra fields."""
    req = LiteLLMRequest(
        model="m",
        messages=[{"role": "user", "content": "Hi"}],
        extra_field="ignored",
    )
    assert req.model == "m"
