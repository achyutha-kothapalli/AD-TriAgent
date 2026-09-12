from __future__ import annotations

import logging

from app.config import Settings
from app.llm import create_llm_client

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
        client = create_llm_client(self.settings)
        try:
            from openai import APIError

            if client is None:
                return fallback
            response = await client.chat.completions.create(
                model=self.settings.llm_model,
                temperature=0.2,
                max_tokens=180,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an autonomous-driving triage assistant. Explain only supplied evidence, do not claim certainty, and request human review.",
                    },
                    {
                        "role": "user",
                        "content": f"Case: {scenario_title}\nTriage: {triage}\nGive a concise evidence-first explanation.",
                    },
                ],
            )
            return response.choices[0].message.content or fallback
        except (APIError, OSError, ValueError) as error:
            logger.info("LLM narrative fallback: %s", error)
            return fallback
        finally:
            if client is not None:
                await client.close()
