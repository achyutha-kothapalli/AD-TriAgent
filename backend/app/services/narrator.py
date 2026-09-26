from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import Settings
from app.llm import create_chat_model

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NarrativeDraft:
    text: str
    source: str
    model: str | None = None
    fallback_reason: str | None = None


class TriageNarrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def draft(self, scenario_title: str, triage: dict) -> NarrativeDraft:
        """Use the configured LLM; deterministic evidence remains the source of truth."""
        fallback = (
            f"{triage['primary_family_label']} is the primary route at {triage['severity']}. "
            f"The decision is based on the extracted 15-second evidence window; human review is required."
        )
        if not self.settings.llm_enabled or not self.settings.llm_api_key:
            return NarrativeDraft(fallback, source="deterministic_fallback", fallback_reason="llm_disabled")
        model = create_chat_model(self.settings)
        try:
            from openai import APIError

            if model is None:
                return NarrativeDraft(
                    fallback, source="deterministic_fallback", fallback_reason="model_not_configured"
                )
            response = await model.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "You are an autonomous-driving triage assistant. Explain only supplied "
                            "evidence, do not claim certainty, and request human review."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"Case: {scenario_title}\nTriage: {triage}\n"
                            "Give a concise evidence-first explanation."
                        )
                    ),
                ]
            )
            if response.content:
                return NarrativeDraft(str(response.content), source="llm", model=self.settings.llm_model)
            return NarrativeDraft(
                fallback, source="deterministic_fallback", fallback_reason="empty_model_response"
            )
        except (APIError, OSError, ValueError) as error:
            logger.info("LLM narrative fallback: %s", error)
            return NarrativeDraft(
                fallback,
                source="deterministic_fallback",
                fallback_reason=type(error).__name__,
            )

    async def explain(self, scenario_title: str, triage: dict) -> str:
        """Compatibility helper for callers that need only the text."""
        return (await self.draft(scenario_title, triage)).text
