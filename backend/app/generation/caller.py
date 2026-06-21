"""
EST Synthesizer — LLM Queue (Rate-Limited, Retryable Caller)
=============================================================

Rate limiting, retry orchestration, and optional schema validation
for LLM calls. The raw LiteLLM interaction lives in ``client.py``.

Exports:
    LLMQueue   — async queue for LLM calls
    queue      — module-level singleton instance
    get_queue  — accessor for the module-level singleton
"""

from __future__ import annotations

import logging
import structlog
from typing import Type

from aiolimiter import AsyncLimiter
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
    before_sleep_log,
)

from backend.app.config import settings
from backend.app.schemas.llm import LLMConfig
from backend.app.generation.client import call_llm, parse_json_response
from backend.app.generation.exceptions import LLMCallError, LLMAPIError, LLMJSONError


# Module-level logger (used by tenacity before_sleep_log)
_logger = logging.getLogger(__name__)

# Module-level structlog logger (used for application logging)
log = structlog.get_logger(__name__)


class LLMQueue:
    """Rate-limited, retryable async queue for LLM calls.

    Usage::

        from backend.app.generation.caller import get_queue

        result = await get_queue().submit(
            system_prompt="...",
            user_prompt="...",
            schema=LLMBatchOutput,
        )
    """

    # -- Constructor --------------------------------------------------

    def __init__(self) -> None:
        self._limiter: AsyncLimiter = AsyncLimiter(
            max_rate=settings.MISTRAL_RATE_LIMIT,
            time_period=1.0,
        )
        self._model: str = settings.LLM_MODEL
        self._config: LLMConfig = LLMConfig(
            model_name=self._model,
            proxy_base_url=settings.LITELLM_PROXY_URL,
            proxy_api_key=settings.MISTRAL_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        self._logger: logging.Logger = logging.getLogger(__name__)

    # -- Public API — submit ------------------------------------------

    async def submit(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel] | None = None,
    ) -> dict:
        """Submit a prompt pair to the LLM and return a parsed dict.

        Rate limiting, retry, and JSON parsing are handled internally.
        Optional Pydantic validation via ``schema``.

        Parameters
        ----------
        system_prompt : str
            System-level instructions.
        user_prompt : str
            Per-request prompt content.
        schema : Type[BaseModel] | None
            Optional Pydantic model to validate the parsed dict.

        Returns
        -------
        dict
            The parsed JSON response as a plain Python dict.

        Raises
        ------
        LLMCallError
            If all retries are exhausted.
        """
        parsed_dict: dict = await self._call_with_retry(system_prompt, user_prompt)

        if schema is not None:
            schema.model_validate(parsed_dict)

        return parsed_dict

    # -- Internal — _call_with_retry ----------------------------------

    @retry(
        stop=stop_after_attempt(settings.LLM_MAX_RETRIES),
        wait=wait_fixed(settings.LLM_RETRY_DELAY_SECONDS),
        retry=retry_if_exception_type((LLMAPIError, LLMJSONError)),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
        reraise=True,
    )
    async def _call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        """Call the LLM with retry + rate limit + JSON parsing.

        Each retry attempt consumes its own rate-limiter token.
        Delegates raw API calls and JSON parsing to ``client.py``.
        """
        await self._limiter.acquire(1)

        raw_content = await call_llm(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            api_key=self._config.proxy_api_key,
            api_base=self._config.proxy_base_url,
        )

        return parse_json_response(raw_content)


# -- Module-level singleton -----------------------------------------------
queue: LLMQueue = LLMQueue()


def get_queue() -> LLMQueue:
    """Return the module-level ``LLMQueue`` singleton."""
    return queue
