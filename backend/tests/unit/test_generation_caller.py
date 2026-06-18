"""Unit tests for backend.app.generation.caller — LLMQueue async singleton, rate limiting, retry, JSON parsing, and schema validation."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pydantic import BaseModel, Field

from backend.app.generation.caller import LLMQueue, get_queue, queue
from backend.app.generation.exceptions import LLMCallError, LLMAPIError, LLMJSONError
from backend.app.schemas.llm import LLMConfig
from backend.app.schemas.question import LLMBatchOutput


class _SimpleSchema(BaseModel):
    """Non-strict schema for testing submit() validation — no enum coercion issues."""
    name: str = Field(...)
    value: int = Field(..., ge=0)


# ── Helpers ──────────────────────────────────────────────────


def _mock_settings():
    """Return a MagicMock mimicking backend.app.config.settings."""
    s = MagicMock()
    s.MISTRAL_API_KEY = "test-key"
    s.MISTRAL_RATE_LIMIT = 5.0
    s.LITELLM_PROXY_URL = "http://localhost:4000"
    s.LLM_MODEL = "mistral/mistral-small-latest"
    s.LLM_TEMPERATURE = 0.3
    s.LLM_MAX_TOKENS = 4096
    s.LLM_MAX_RETRIES = 3
    s.LLM_RETRY_DELAY_SECONDS = 2
    return s


def _fresh_queue():
    """Create a fresh LLMQueue with patched settings."""
    with patch("backend.app.generation.caller.settings", _mock_settings()):
        return LLMQueue()


def _valid_batch_dict():
    """Return a minimal valid dict matching LLMBatchOutput schema."""
    return {
        "reasoning": "The passage discusses common English conventions.",
        "questions": [
            {
                "question_text": "Which underlined portion contains an error?",
                "choices": [
                    {"letter": "A", "text": "NO CHANGE", "distractor_role": "best_answer"},
                    {"letter": "B", "text": "runs fast", "distractor_role": "good_not_best"},
                    {"letter": "C", "text": "running quick", "distractor_role": "completely_wrong"},
                    {"letter": "D", "text": "ran quickly", "distractor_role": "completely_wrong"},
                ],
                "correct_answer": "A",
                "explanation": "The original is correct.",
                "supporting_line": "The cat sat on the mat.",
                "skill_type": "conventions_of_standard_english",
                "difficulty": "medium",
            }
        ],
    }


def _mock_litellm_response(content: str) -> MagicMock:
    """Build a MagicMock mimicking a litellm completion response object."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ── Exception hierarchy ─────────────────────────────────────


def test_llm_call_error_is_exception():
    assert issubclass(LLMCallError, Exception)


def test_llm_api_error_inherits_call_error():
    assert issubclass(LLMAPIError, LLMCallError)


def test_llm_json_error_inherits_call_error():
    assert issubclass(LLMJSONError, LLMCallError)


def test_llm_api_error_and_json_error_are_distinct():
    assert not issubclass(LLMAPIError, LLMJSONError)
    assert not issubclass(LLMJSONError, LLMAPIError)


def test_llm_call_error_message():
    e = LLMCallError("base failure")
    assert str(e) == "base failure"


def test_llm_api_error_message():
    e = LLMAPIError("api failure")
    assert str(e) == "api failure"


def test_llm_json_error_message():
    e = LLMJSONError("json failure")
    assert str(e) == "json failure"


# ── Singleton pattern ───────────────────────────────────────


def test_get_queue_returns_queue_instance():
    from backend.app.generation.caller import get_queue
    q = get_queue()
    assert isinstance(q, LLMQueue)


def test_queue_is_module_singleton():
    from backend.app.generation.caller import queue as q1
    from backend.app.generation.caller import queue as q2
    assert q1 is q2


# ── Constructor / configuration ──────────────────────────────


def test_limiter_max_rate_matches_settings():
    q = _fresh_queue()
    assert q._limiter.max_rate == 5.0


def test_model_name_is_mistral_small_latest():
    q = _fresh_queue()
    assert q._model == "mistral/mistral-small-latest"


def test_config_proxy_api_key_matches_settings():
    q = _fresh_queue()
    assert q._config.proxy_api_key == "test-key"


def test_config_proxy_base_url():
    q = _fresh_queue()
    assert q._config.proxy_base_url == "http://localhost:4000"


def test_config_temperature():
    q = _fresh_queue()
    assert q._config.temperature == 0.3


def test_config_max_tokens():
    q = _fresh_queue()
    assert q._config.max_tokens == 4096


def test_config_model_name_matches_model_attr():
    q = _fresh_queue()
    assert q._config.model_name == q._model


def test_logger_is_module_logger():
    q = _fresh_queue()
    assert q._logger.name == "backend.app.generation.caller"


# ── submit() — happy path ───────────────────────────────────


async def test_submit_returns_parsed_dict_on_valid_json():
    q = _fresh_queue()
    q._call_with_retry = AsyncMock(return_value=_valid_batch_dict())
    result = await q.submit(system_prompt="sys", user_prompt="usr")
    assert result == _valid_batch_dict()


async def test_submit_passes_prompts_to_call_with_retry():
    q = _fresh_queue()
    q._call_with_retry = AsyncMock(return_value=_valid_batch_dict())
    await q.submit(system_prompt="SYS", user_prompt="USR")
    q._call_with_retry.assert_called_once_with("SYS", "USR")


async def test_submit_does_not_acquire_limiter_directly():
    q = _fresh_queue()
    q._limiter.acquire = AsyncMock()
    q._call_with_retry = AsyncMock(return_value=_valid_batch_dict())
    await q.submit(system_prompt="s", user_prompt="u")
    q._limiter.acquire.assert_not_called()


async def test_call_with_retry_acquires_limiter():
    q = _fresh_queue()
    q._limiter.acquire = AsyncMock()
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=_mock_litellm_response(json.dumps({"ok": True})))):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            await q._call_with_retry(system_prompt="s", user_prompt="u")
    q._limiter.acquire.assert_called_once_with(1)


# ── submit() — error propagation ────────────────────────────


async def test_submit_propagates_llm_json_error():
    """submit() propagates LLMJSONError raised inside _call_with_retry."""
    q = _fresh_queue()
    q._call_with_retry = AsyncMock(side_effect=LLMJSONError("Invalid JSON from LLM: expect"))
    with pytest.raises(LLMJSONError, match="Invalid JSON from LLM"):
        await q.submit(system_prompt="s", user_prompt="u")


async def test_submit_propagates_llm_api_error():
    """submit() propagates LLMAPIError raised inside _call_with_retry."""
    q = _fresh_queue()
    q._call_with_retry = AsyncMock(side_effect=LLMAPIError("Empty response from LLM"))
    with pytest.raises(LLMAPIError, match="Empty response from LLM"):
        await q.submit(system_prompt="s", user_prompt="u")


# ── submit() — schema validation ────────────────────────────


async def test_submit_with_schema_validates_successfully():
    q = _fresh_queue()
    valid_dict = {"name": "test", "value": 42}
    q._call_with_retry = AsyncMock(return_value=valid_dict)
    result = await q.submit(system_prompt="s", user_prompt="u", schema=_SimpleSchema)
    assert result == valid_dict


async def test_submit_with_schema_raises_validation_error_on_bad_data():
    q = _fresh_queue()
    bad_dict = {"name": "test", "value": -1}  # value < 0 violates ge=0
    q._call_with_retry = AsyncMock(return_value=bad_dict)
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        await q.submit(system_prompt="s", user_prompt="u", schema=_SimpleSchema)


async def test_submit_without_schema_skips_validation():
    q = _fresh_queue()
    weird_dict = {"anything": "goes", "no": "questions field"}
    q._call_with_retry = AsyncMock(return_value=weird_dict)
    result = await q.submit(system_prompt="s", user_prompt="u")
    assert result == weird_dict


async def test_submit_returns_dict_not_pydantic_model():
    q = _fresh_queue()
    valid_dict = {"name": "test", "value": 42}
    q._call_with_retry = AsyncMock(return_value=valid_dict)
    result = await q.submit(system_prompt="s", user_prompt="u", schema=_SimpleSchema)
    assert isinstance(result, dict)
    assert not isinstance(result, _SimpleSchema)


# ── _call_with_retry() — litellm integration ─────────────────


async def test_call_with_retry_returns_content_on_success():
    q = _fresh_queue()
    expected_dict = {"result": "hello"}
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=_mock_litellm_response(json.dumps(expected_dict)))) as mock_ac:
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            result = await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert result == expected_dict


async def test_call_with_retry_raises_llm_api_error_on_empty_response():
    q = _fresh_queue()
    empty_resp = _mock_litellm_response("")
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=empty_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMAPIError, match="Empty response from LLM"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")


async def test_call_with_retry_raises_llm_api_error_on_none_content():
    q = _fresh_queue()
    none_resp = MagicMock()
    none_resp.choices = [MagicMock(message=MagicMock(content=None))]
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=none_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMAPIError, match="Empty response from LLM"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")


async def test_call_with_retry_passes_model_and_messages():
    q = _fresh_queue()
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=_mock_litellm_response(json.dumps({"ok": True})))) as mock_ac:
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            await q._call_with_retry(system_prompt="SYS", user_prompt="USR")
    mock_ac.assert_called_once()
    call_kwargs = mock_ac.call_args[1]
    assert call_kwargs["model"] == "mistral/mistral-small-latest"
    assert call_kwargs["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]


async def test_call_with_retry_passes_config_values():
    q = _fresh_queue()
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=_mock_litellm_response(json.dumps({"ok": True})))) as mock_ac:
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            await q._call_with_retry(system_prompt="s", user_prompt="u")
    call_kwargs = mock_ac.call_args[1]
    assert call_kwargs["temperature"] == 0.3
    assert call_kwargs["max_tokens"] == 4096
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert call_kwargs["api_key"] == "test-key"
    assert call_kwargs["api_base"] == "http://localhost:4000"


async def test_call_with_retry_raises_on_litellm_exception():
    q = _fresh_queue()
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(side_effect=Exception("network down"))):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(Exception, match="network down"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")


# ── Retry behavior ──────────────────────────────────────────


async def test_retry_retries_on_llm_api_error_up_to_3_attempts():
    q = _fresh_queue()
    call_count = 0

    async def _fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise LLMAPIError("transient failure")

    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(side_effect=_fail)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMAPIError, match="transient failure"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert call_count == 3


async def test_retry_retries_on_llm_json_error_up_to_3_attempts():
    q = _fresh_queue()
    call_count = 0

    async def _fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise LLMJSONError("bad json")

    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(side_effect=_fail)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMJSONError, match="bad json"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert call_count == 3


async def test_retry_does_not_retry_on_base_llm_call_error():
    q = _fresh_queue()
    call_count = 0

    async def _fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise LLMCallError("non-retryable")

    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(side_effect=_fail)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMCallError, match="non-retryable"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert call_count == 1


async def test_retry_succeeds_on_second_attempt():
    q = _fresh_queue()
    call_count = 0

    async def _eventually_succeed(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise LLMAPIError("transient")
        return _mock_litellm_response(json.dumps(_valid_batch_dict()))

    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(side_effect=_eventually_succeed)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            result = await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert call_count == 2
    assert isinstance(result, dict)


# ── Edge cases ───────────────────────────────────────────────


async def test_call_with_retry_whitespace_only_content_raises_api_error():
    q = _fresh_queue()
    ws_resp = _mock_litellm_response("   ")
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=ws_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMAPIError, match="Empty response from LLM"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")


async def test_call_with_retry_raises_llm_json_error_on_non_json_content():
    """_call_with_retry raises LLMJSONError when litellm returns non-JSON text."""
    q = _fresh_queue()
    non_json_resp = _mock_litellm_response("not json at all")
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=non_json_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMJSONError, match="Invalid JSON from LLM"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")


async def test_call_with_retry_accepts_json_with_trailing_whitespace():
    """json.loads handles trailing whitespace naturally — _call_with_retry strips then parses."""
    q = _fresh_queue()
    valid_dict = _valid_batch_dict()
    valid_json = json.dumps(valid_dict) + "  \n  "
    ws_resp = _mock_litellm_response(valid_json)
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=ws_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            result = await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert result == valid_dict


async def test_call_with_retry_accepts_nested_json():
    """Nested JSON with embedded quotes is parsed correctly by _call_with_retry."""
    q = _fresh_queue()
    nested_dict = _valid_batch_dict()
    nested_dict["questions"][0]["explanation"] = "See section 2.1:\n\"The original is correct.\""
    nested_json = json.dumps(nested_dict)
    nested_resp = _mock_litellm_response(nested_json)
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=nested_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            result = await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert result["questions"][0]["explanation"] == "See section 2.1:\n\"The original is correct.\""


async def test_call_with_retry_empty_string_raises_api_error():
    """Empty string content is treated as empty response → LLMAPIError."""
    q = _fresh_queue()
    empty_resp = _mock_litellm_response("")
    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=empty_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMAPIError, match="Empty response from LLM"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")


def test_get_queue_returns_same_object_as_module_queue():
    """Module-level get_queue() returns the same object as the module-level `queue`."""
    from backend.app.generation.caller import get_queue, queue
    assert get_queue() is queue


# -- client.call_llm + parse_json_response ---------------------------

async def test_call_llm_returns_content_on_success():
    from backend.app.generation.client import call_llm

    with patch("backend.app.generation.client.litellm.acompletion", new=AsyncMock(return_value=_mock_litellm_response(json.dumps({"ok": True})))) as mock_ac:
        result = await call_llm(
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.3,
            max_tokens=100,
            api_key="key",
            api_base="http://localhost:4000",
        )
    assert result == json.dumps({"ok": True})


def test_parse_json_response_parses_valid_json():
    from backend.app.generation.client import parse_json_response

    result = parse_json_response('{"name": "test"}')
    assert result == {"name": "test"}


def test_parse_json_response_raises_on_invalid():
    from backend.app.generation.client import parse_json_response

    with pytest.raises(LLMJSONError, match="Invalid JSON"):
        parse_json_response("not json")
