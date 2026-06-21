"""
EST Synthesizer — Raw LiteLLM Client
======================================

Thin wrapper around ``litellm.acompletion`` for EST question generation.

This module owns the raw LLM API interaction and JSON parsing — it knows
nothing about rate limiting, retry orchestration, or schema validation.
Those concerns live in ``caller.py``.

Exports:
    call_llm          — raw litellm.acompletion call, returns content string
    parse_json_response — validates and parses JSON from content string
"""

from __future__ import annotations

import json
import structlog

import litellm

from backend.app.generation.exceptions import LLMAPIError, LLMJSONError

_logger = structlog.get_logger(__name__)


async def call_llm(
    model: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    api_key: str,
    api_base: str,
) -> str:
    """Call the LLM via LiteLLM and return the raw response text.

    Parameters
    ----------
    model : str
        LiteLLM model identifier (e.g. ``"mistral/mistral-small-latest"``).
    messages : list
        Chat messages as ``[{"role": ..., "content": ...}, ...]``.
    temperature : float
        LLM temperature (0.0–2.0).
    max_tokens : int
        Maximum output tokens.
    api_key : str
        API key for the LLM provider or LiteLLM proxy.
    api_base : str
        Base URL for the LiteLLM proxy.

    Returns
    -------
    str
        The raw response content string.

    Raises
    ------
    LLMAPIError
        If the response is empty or None.
    """
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        api_key=api_key,
        api_base=api_base,
    )

    content: str | None = response.choices[0].message.content
    if content is None or content.strip() == "":
        raise LLMAPIError("Empty response from LLM")

    return content


def parse_json_response(content: str) -> dict:
    """Parse a raw content string into a Python dict.

    Parameters
    ----------
    content : str
        Raw response text from the LLM (should be valid JSON).

    Returns
    -------
    dict
        The parsed JSON content.

    Raises
    ------
    LLMJSONError
        If the content is not valid JSON.
    """
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        _logger.error(
            "Failed to parse LLM response as JSON",
            error=exc,
            raw_text=content[:200],
        )
        raise LLMJSONError(f"Invalid JSON from LLM: {exc}") from exc
