"""
EST Synthesizer - LLM Models
==============================
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LLMConfig(BaseModel):
    """Configuration for calling a model through the LiteLLM proxy."""

    model_config = ConfigDict(strict=True)

    model_name: str = Field(
        ..., description="Model identifier passed to LiteLLM (e.g. 'freetheai-smart')"
    )
    proxy_base_url: str = Field(
        default="http://localhost:4000",
        description="LiteLLM proxy endpoint",
    )
    proxy_api_key: str = Field(
        default="sk-1234",
        description="LiteLLM proxy master key",
    )
    temperature: float = Field(
        default=0.3, ge=0.0, le=2.0, description="LLM temperature"
    )
    max_tokens: int = Field(
        default=4096, ge=1, description="Maximum output tokens"
    )


class LiteLLMRequest(BaseModel):
    """Payload sent to LiteLLM proxy's /chat/completions endpoint."""

    model_config = ConfigDict(strict=True)

    model: str = Field(..., description="Model name as known to proxy")
    messages: list = Field(
        ..., min_length=1, description="Chat messages: list of {role, content} dicts"
    )
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    response_format: Optional[dict] = Field(
        default=None,
        description="Structured output format, e.g. {'type': 'json_object'}",
    )