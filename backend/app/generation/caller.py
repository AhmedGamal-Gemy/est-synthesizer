"""
EST Synthesizer — LLM Queue (Rate-Limited, Retryable Caller)
=============================================================

This module provides the ``LLMQueue`` class — an async singleton that
manages all outbound calls to the LLM (Mistral via LiteLLM proxy).

Key design decisions:

- **Singleton pattern** — one ``LLMQueue`` instance per process, accessed
  via ``LLMQueue.get_instance()``. This ensures a single shared rate limiter
  so the global API throughput cap is respected across all concurrent callers.

- **Rate limiting** — an ``aiolimiter.AsyncLimiter`` throttles outbound
  requests to ``settings.MISTRAL_RATE_LIMIT`` (default 1 req/s for the
  free Mistral tier). The limiter is acquired *before* every API call,
  guaranteeing the contract even under concurrent ``submit()`` calls.

- **Retry with tenacity** — transient API errors (network failures, empty
  responses, JSON parse errors) are retried up to 3 times with a fixed
  2-second back-off. Only ``LLMAPIError`` and ``LLMJSONError`` trigger
  retries; ``LLMCallError`` (the base class) is not retryable by default.

- **JSON-mode output** — ``response_format={"type": "json_object"}`` forces
  the model to return valid JSON, eliminating the need to strip markdown
  fences or handle mixed text/JSON responses.

- **Optional Pydantic validation** — callers may pass a ``schema``
  (a ``BaseModel`` subclass) to validate the parsed JSON dict. The raw
  dict is always returned so downstream code has full flexibility.

Exports:

    LLMQueue       — async singleton for LLM calls
"""

from __future__ import annotations

import json
import logging
from typing import Optional, Type

from aiolimiter import AsyncLimiter
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
    before_sleep_log,
)
import litellm

from backend.app.config import settings
from backend.app.schemas.llm import LLMConfig
from backend.app.generation.exceptions import LLMCallError, LLMAPIError, LLMJSONError


# ---------------------------------------------------------------------------
# LLMQueue — async singleton
# ---------------------------------------------------------------------------

class LLMQueue:
    """Rate-limited, retryable async queue for LLM calls.

    Usage::

        queue = LLMQueue.get_instance()
        result = await queue.submit(
            system_prompt="You are an expert...",
            user_prompt="<PASSAGE>...",
            schema=LLMBatchOutput,
        )

    The singleton pattern ensures one shared ``AsyncLimiter`` across
    the entire process, so concurrent callers cannot exceed the global
    rate cap.

    Attributes
    ----------
    _instance : Optional[LLMQueue]
        Class-level singleton holder. ``None`` until first
        ``get_instance()`` call.
    _limiter : AsyncLimiter
        Token-bucket rate limiter initialised from
        ``settings.MISTRAL_RATE_LIMIT``.
    _model : str
        LiteLLM model identifier (``"mistral/mistral-small-latest"``).
    _config : LLMConfig
        Full LLM configuration (model name, proxy URL, API key,
        temperature, max tokens).
    _logger : logging.Logger
        Module-level logger for retry, error, and lifecycle events.
    """

    _instance: Optional[LLMQueue] = None

    # -------------------------------------------------------------------
    # Singleton factory
    # -------------------------------------------------------------------

    @staticmethod
    def get_instance() -> LLMQueue:
        """Return the singleton ``LLMQueue`` instance.

        Creates the instance on first call; returns the cached instance
        on subsequent calls. This avoids multiple rate limiter objects
        that could individually exceed the global API throughput cap.

        Returns
        -------
        LLMQueue
            The process-wide singleton instance.
        """
        if LLMQueue._instance is None:
            LLMQueue._instance = LLMQueue()
        return LLMQueue._instance

    # -------------------------------------------------------------------
    # Constructor
    # -------------------------------------------------------------------

    def __init__(self) -> None:
        """Initialise the LLM queue with rate limiter and config.

        Called only once (via ``get_instance()``). Sets up:

        - ``_limiter`` — ``AsyncLimiter`` throttled to
          ``settings.MISTRAL_RATE_LIMIT`` requests per second.
        - ``_model`` — LiteLLM model name string.
        - ``_config`` — ``LLMConfig`` with proxy URL, API key,
          temperature, and max tokens.
        - ``_logger`` — module logger for lifecycle and retry events.
        """
        self._limiter: AsyncLimiter = AsyncLimiter(
            max_rate=settings.MISTRAL_RATE_LIMIT,
            time_period=1.0,
        )
        self._model: str = "mistral/mistral-small-latest"
        self._config: LLMConfig = LLMConfig(
            model_name=self._model,
            proxy_base_url="http://localhost:4000",
            proxy_api_key=settings.MISTRAL_API_KEY,
            temperature=0.3,
            max_tokens=4096,
        )
        self._logger: logging.Logger = logging.getLogger(__name__)

    # -------------------------------------------------------------------
    # Public API — submit
    # -------------------------------------------------------------------

    async def submit(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel] | None = None,
    ) -> dict:
        """Submit a prompt pair to the LLM and return a parsed dict.

        This is the main entry point for all LLM interactions in the
        pipeline. It enforces rate limiting, retries transient failures,
        and optionally validates the response against a Pydantic schema.

        Flow::

            1. Acquire rate-limiter slot (await ``_limiter``)
            2. Call LLM with retry wrapper → raw text response
            3. Parse JSON from the raw text → dict
            4. If ``schema`` is given, validate dict through it
            5. Return the raw dict (not the Pydantic model instance)

        Parameters
        ----------
        system_prompt : str
            System-level instructions (role, rules, output format).
        user_prompt : str
            Per-request prompt (passage, examples, task, state).
        schema : Type[BaseModel] | None
            Optional Pydantic model class to validate the parsed
            dict against. When provided, ``schema.model_validate()``
            is called to ensure structural correctness, but the raw
            dict is returned (not the model instance) for downstream
            flexibility.

        Returns
        -------
        dict
            The parsed JSON response as a plain Python dict.

        Raises
        ------
        LLMCallError
            If the LLM call fails after all retries are exhausted.
        LLMJSONError
            If the response text cannot be parsed as valid JSON.
        LLMAPIError
            If the API returns an empty or unusable response.
        """
        # ── 1. Rate-limit gate ────────────────────────────────────────
        await self._limiter.acquire(1)

        # ── 2. LLM call with retry ───────────────────────────────────
        raw_text: str = await self._call_with_retry(system_prompt, user_prompt)

        # ── 3. JSON parsing ──────────────────────────────────────────
        try:
            parsed_dict: dict = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError) as exc:
            self._logger.error(
                "Failed to parse LLM response as JSON: %s | raw_text=%s",
                exc,
                raw_text[:200],
            )
            raise LLMJSONError(
                f"Invalid JSON from LLM: {exc}"
            ) from exc

        # ── 4. Optional Pydantic validation ──────────────────────────
        if schema is not None:
            schema.model_validate(parsed_dict)

        # ── 5. Return raw dict ───────────────────────────────────────
        return parsed_dict

    # -------------------------------------------------------------------
    # Internal — _call_with_retry
    # -------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type((LLMAPIError, LLMJSONError)),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    async def _call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Call the LLM with tenacity retry decoration.

        This method is the retry boundary. Tenacity retries on
        ``LLMAPIError`` and ``LLMJSONError`` up to 3 times with a
        fixed 2-second wait between attempts. All other exceptions
        (including the base ``LLMCallError``) propagate immediately.

        Parameters
        ----------
        system_prompt : str
            System-level instructions for the model.
        user_prompt : str
            User-level prompt content.

        Returns
        -------
        str
            The raw text content from the model's response.

        Raises
        ------
        LLMAPIError
            If the API call fails or returns an empty response.
        """
        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            response_format={"type": "json_object"},
            api_key=settings.MISTRAL_API_KEY,
        )

        # ── Extract text ─────────────────────────────────────────────
        content: str | None = response.choices[0].message.content
        if content is None or content.strip() == "":
            raise LLMAPIError("Empty response from LLM")

        return content
