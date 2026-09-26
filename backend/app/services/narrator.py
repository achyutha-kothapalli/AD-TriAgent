from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import Settings
from app.llm import create_chat_model

logger = logging.getLogger(__name__)

class TriageNarrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def explain(self, scenario_title: str, triage: dict) -> str:
        """Use the configured LLM; deterministic evidence remains the source of truth."""
        fallback = (
            f"{triage['primary_family_label']} is the primary route at {triage['severity']}. "
            f"The decision is based on the extracted 15-second evidence window; human review is required."
        )
        if not self.settings.llm_enabled or not self.settings.llm_api_key:
            return fallback
        model = create_chat_model(self.settings)
        try:
            from openai import APIError

            if model is None:
                return fallback
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
            return str(response.content) if response.content else fallback
        except (APIError, OSError, ValueError) as error:
            logger.info("LLM narrative fallback: %s", error)
            return fallback
