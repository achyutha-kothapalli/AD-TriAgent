from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from app.config import Settings


def llm_client_options(settings: Settings) -> dict[str, Any] | None:
    """Return OpenAI-compatible client options without exposing secrets to callers."""
    if not settings.llm_api_key:
        return None

    options: dict[str, Any] = {"api_key": settings.llm_api_key}
    if settings.llm_base_url and settings.llm_base_url.strip():
        options["base_url"] = settings.llm_base_url.strip()
    return options


def create_chat_model(settings: Settings) -> ChatOpenAI | None:
    """Create LangChain's OpenAI-compatible chat model without exposing credentials."""
    options = llm_client_options(settings)
    if not options or not settings.llm_model:
        return None
    return ChatOpenAI(model=settings.llm_model, temperature=0.2, max_tokens=180, **options)
