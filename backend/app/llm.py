from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.config import Settings


def llm_client_options(settings: Settings) -> dict[str, Any] | None:
    """Return OpenAI-compatible client options without exposing secrets to callers."""
    if not settings.llm_api_key:
        return None

    options: dict[str, Any] = {"api_key": settings.llm_api_key}
    if settings.llm_base_url and settings.llm_base_url.strip():
        options["base_url"] = settings.llm_base_url.strip()
    return options


def create_llm_client(settings: Settings) -> AsyncOpenAI | None:
    """Create the configured server-side, OpenAI-compatible LLM client."""
    options = llm_client_options(settings)
    return AsyncOpenAI(**options) if options else None
