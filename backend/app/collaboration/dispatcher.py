from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class CollaborationDispatcher:
    """Best-effort mirror of case events; the local case timeline is authoritative."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def dispatch(self, case: dict[str, Any], event: dict[str, str]) -> list[dict[str, str]]:
        outcomes = [
            {"connector": "local", "status": "recorded"},
            await self._slack(case, event),
            await self._ambiguous(case, event),
        ]
        return outcomes

    async def _slack(self, case: dict[str, Any], event: dict[str, str]) -> dict[str, str]:
        if not self.settings.slack_webhook_url:
            return {"connector": "slack", "status": "not_configured"}
        message = f"[AD triage {case['id']}] {event['actor']}: {event['message']}"
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(self.settings.slack_webhook_url, json={"text": message})
                response.raise_for_status()
            return {"connector": "slack", "status": "sent"}
        except httpx.HTTPError:
            return {"connector": "slack", "status": "failed"}

    async def _ambiguous(self, case: dict[str, Any], event: dict[str, str]) -> dict[str, str]:
        """Portable event contract; map the endpoint to your Ambiguous workspace transport."""
        if not (self.settings.ambiguous_api_base_url and self.settings.ambiguous_api_token):
            return {"connector": "ambiguous", "status": "not_configured"}
        payload = {
            "workspace_id": self.settings.ambiguous_workspace_id,
            "case_id": case["id"],
            "title": case["scenario_title"],
            "triage": case["triage"],
            "event": event,
        }
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(
                    f"{self.settings.ambiguous_api_base_url.rstrip('/')}/case-events",
                    headers={"Authorization": f"Bearer {self.settings.ambiguous_api_token}"},
                    json=payload,
                )
                response.raise_for_status()
            return {"connector": "ambiguous", "status": "sent"}
        except httpx.HTTPError:
            return {"connector": "ambiguous", "status": "failed"}
