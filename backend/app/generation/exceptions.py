"""EST Synthesizer — LLM Call Exceptions."""
from __future__ import annotations


class LLMCallError(Exception):
    """Base exception for LLM call failures.

    All LLM-related errors in the pipeline inherit from this class.
    It is *not* retryable by default — only its subclasses
    ``LLMAPIError`` and ``LLMJSONError`` trigger tenacity retries.
    """


class LLMAPIError(LLMCallError):
    """API / network errors during LLM calls.

    These are retryable — transient failures like rate-limit responses,
    network timeouts, or empty model outputs fall under this category.
    """


class LLMJSONError(LLMCallError):
    """JSON parse or validation errors from LLM responses.

    Retryable — the model may occasionally produce malformed JSON,
    and a second attempt often succeeds (especially with
    ``response_format={"type": "json_object"}`` enforced).
    """
