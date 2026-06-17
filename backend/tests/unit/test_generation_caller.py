"""Unit tests for backend.app.generation.caller — LLMQueue async singleton, rate limiting, retry, JSON parsing, and schema validation."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pydantic import BaseModel, Field

from backend.app.generation.caller import LLMQueue
from backend.app.generation.exceptions import LLMCallError, LLMAPIError, LLMJSONError
from backend.app.schemas.llm import LLMConfig
from backend.app.schemas.question import LLMBatchOutput


class _SimpleSchema(BaseModel):
    """Non-strict schema for testing submit() validation — no enum coercion issues."""
    name: str = Field(...)
    value: int = Field(..., ge=0)


# ── Helpers ──────────────────────────────────────────────────


def _reset_singleton():
    """Reset the LLMQueue singleton so get_instance() creates a fresh object."""
    LLMQueue._instance = None


def _mock_settings():
    """Return a MagicMock mimicking backend.app.config.settings."""
    s = MagicMock()
    s.MISTRAL_API_KEY = "test-key"
    s.MISTRAL_RATE_LIMIT = 5.0
    return s


def _fresh_queue():
    """Create a fresh LLMQueue with patched settings."""
    _reset_singleton()
    with patch("backend.app.generation.caller.settings", _mock_settings()):
        return LLMQueue.get_instance()


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


def test_get_instance_creates_queue():
    _reset_singleton()
    with patch("backend.app.generation.caller.settings", _mock_settings()):
        q = LLMQueue.get_instance()
    assert q is not None
    assert isinstance(q, LLMQueue)


def test_get_instance_returns_same_object():
    _reset_singleton()
    with patch("backend.app.generation.caller.settings", _mock_settings()):
        q1 = LLMQueue.get_instance()
        q2 = LLMQueue.get_instance()
    assert q1 is q2


def test_singleton_reset_creates_new_instance():
    _reset_singleton()
    with patch("backend.app.generation.caller.settings", _mock_settings()):
        q1 = LLMQueue.get_instance()
    _reset_singleton()
    with patch("backend.app.generation.caller.settings", _mock_settings()):
        q2 = LLMQueue.get_instance()
    assert q1 is not q2


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
    valid_json = json.dumps(_valid_batch_dict())
    q._call_with_retry = AsyncMock(return_value=valid_json)
    result = await q.submit(system_prompt="sys", user_prompt="usr")
    assert result == _valid_batch_dict()


async def test_submit_passes_prompts_to_call_with_retry():
    q = _fresh_queue()
    q._call_with_retry = AsyncMock(return_value=json.dumps(_valid_batch_dict()))
    await q.submit(system_prompt="SYS", user_prompt="USR")
    q._call_with_retry.assert_called_once_with("SYS", "USR")


async def test_submit_acquires_limiter():
    q = _fresh_queue()
    q._limiter.acquire = AsyncMock()
    q._call_with_retry = AsyncMock(return_value=json.dumps(_valid_batch_dict()))
    await q.submit(system_prompt="s", user_prompt="u")
    q._limiter.acquire.assert_called_once_with(1)


async def test_submit_limiter_acquired_before_call():
    q = _fresh_queue()
    call_order = []
    q._limiter.acquire = AsyncMock(side_effect=lambda n: call_order.append("limiter"))
    q._call_with_retry = AsyncMock(side_effect=lambda s, u: (call_order.append("call"), json.dumps({"ok": True}))[-1])
    await q.submit(system_prompt="s", user_prompt="u")
    assert call_order == ["limiter", "call"]


# ── submit() — JSON parsing errors ──────────────────────────


async def test_submit_raises_llm_json_error_on_invalid_json():
    q = _fresh_queue()
    q._call_with_retry = AsyncMock(return_value="not json at all")
    with pytest.raises(LLMJSONError, match="Invalid JSON from LLM"):
        await q.submit(system_prompt="s", user_prompt="u")


async def test_submit_json_error_wraps_json_decode_error():
    q = _fresh_queue()
    q._call_with_retry = AsyncMock(return_value="{broken")
    with pytest.raises(LLMJSONError) as exc_info:
        await q.submit(system_prompt="s", user_prompt="u")
    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


async def test_submit_logs_error_on_json_failure(caplog):
    q = _fresh_queue()
    q._call_with_retry = AsyncMock(return_value="not json")
    with caplog.at_level(logging.ERROR, logger="backend.app.generation.caller"):
        with pytest.raises(LLMJSONError):
            await q.submit(system_prompt="s", user_prompt="u")
    assert any("Failed to parse LLM response as JSON" in r.message for r in caplog.records)


# ── submit() — schema validation ────────────────────────────


async def test_submit_with_schema_validates_successfully():
    q = _fresh_queue()
    valid_dict = {"name": "test", "value": 42}
    valid_json = json.dumps(valid_dict)
    q._call_with_retry = AsyncMock(return_value=valid_json)
    result = await q.submit(system_prompt="s", user_prompt="u", schema=_SimpleSchema)
    assert result == valid_dict


async def test_submit_with_schema_raises_validation_error_on_bad_data():
    q = _fresh_queue()
    bad_dict = {"name": "test", "value": -1}  # value < 0 violates ge=0
    q._call_with_retry = AsyncMock(return_value=json.dumps(bad_dict))
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        await q.submit(system_prompt="s", user_prompt="u", schema=_SimpleSchema)


async def test_submit_without_schema_skips_validation():
    q = _fresh_queue()
    weird_dict = {"anything": "goes", "no": "questions field"}
    q._call_with_retry = AsyncMock(return_value=json.dumps(weird_dict))
    result = await q.submit(system_prompt="s", user_prompt="u")
    assert result == weird_dict


async def test_submit_returns_dict_not_pydantic_model():
    q = _fresh_queue()
    valid_dict = {"name": "test", "value": 42}
    valid_json = json.dumps(valid_dict)
    q._call_with_retry = AsyncMock(return_value=valid_json)
    result = await q.submit(system_prompt="s", user_prompt="u", schema=_SimpleSchema)
    assert isinstance(result, dict)
    assert not isinstance(result, _SimpleSchema)


# ── _call_with_retry() — litellm integration ─────────────────


async def test_call_with_retry_returns_content_on_success():
    q = _fresh_queue()
    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(return_value=_mock_litellm_response("hello"))) as mock_ac:
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            result = await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert result == "hello"


async def test_call_with_retry_raises_llm_api_error_on_empty_response():
    q = _fresh_queue()
    empty_resp = _mock_litellm_response("")
    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(return_value=empty_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMAPIError, match="Empty response from LLM"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")


async def test_call_with_retry_raises_llm_api_error_on_none_content():
    q = _fresh_queue()
    none_resp = MagicMock()
    none_resp.choices = [MagicMock(message=MagicMock(content=None))]
    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(return_value=none_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMAPIError, match="Empty response from LLM"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")


async def test_call_with_retry_passes_model_and_messages():
    q = _fresh_queue()
    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(return_value=_mock_litellm_response("ok"))) as mock_ac:
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
    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(return_value=_mock_litellm_response("ok"))) as mock_ac:
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            await q._call_with_retry(system_prompt="s", user_prompt="u")
    call_kwargs = mock_ac.call_args[1]
    assert call_kwargs["temperature"] == 0.3
    assert call_kwargs["max_tokens"] == 4096
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert call_kwargs["api_key"] == "test-key"


async def test_call_with_retry_raises_on_litellm_exception():
    q = _fresh_queue()
    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(side_effect=Exception("network down"))):
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

    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(side_effect=_fail)):
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

    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(side_effect=_fail)):
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

    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(side_effect=_fail)):
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

    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(side_effect=_eventually_succeed)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            result = await q._call_with_retry(system_prompt="s", user_prompt="u")
    assert call_count == 2
    assert isinstance(result, str)


# ── Edge cases ───────────────────────────────────────────────


async def test_submit_with_whitespace_only_json_string():
    q = _fresh_queue()
    # json.loads accepts whitespace-only strings as valid (returns None-like or error)
    # Actually json.loads("   ") raises JSONDecodeError, so this should raise LLMJSONError
    q._call_with_retry = AsyncMock(return_value="   ")
    with pytest.raises(LLMJSONError):
        await q.submit(system_prompt="s", user_prompt="u")


async def test_submit_with_valid_json_but_trailing_whitespace():
    q = _fresh_queue()
    valid_json = json.dumps(_valid_batch_dict()) + "  \n  "
    q._call_with_retry = AsyncMock(return_value=valid_json)
    result = await q.submit(system_prompt="s", user_prompt="u")
    assert result == _valid_batch_dict()


async def test_submit_with_nested_json():
    q = _fresh_queue()
    nested_dict = _valid_batch_dict()
    nested_dict["questions"][0]["explanation"] = "See section 2.1:\n\"The original is correct.\""
    valid_json = json.dumps(nested_dict)
    q._call_with_retry = AsyncMock(return_value=valid_json)
    result = await q.submit(system_prompt="s", user_prompt="u")
    assert result["questions"][0]["explanation"] == "See section 2.1:\n\"The original is correct.\""


async def test_submit_raises_on_empty_string_response():
    q = _fresh_queue()
    # Empty string is not valid JSON
    q._call_with_retry = AsyncMock(return_value="")
    with pytest.raises(LLMJSONError):
        await q.submit(system_prompt="s", user_prompt="u")


async def test_call_with_retry_whitespace_only_content_raises_api_error():
    q = _fresh_queue()
    ws_resp = _mock_litellm_response("   ")
    with patch("backend.app.generation.caller.litellm.acompletion", new=AsyncMock(return_value=ws_resp)):
        with patch("backend.app.generation.caller.settings", _mock_settings()):
            with pytest.raises(LLMAPIError, match="Empty response from LLM"):
                await q._call_with_retry(system_prompt="s", user_prompt="u")
