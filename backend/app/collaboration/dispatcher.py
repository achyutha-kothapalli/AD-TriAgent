from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class SlackNotifier:
    """Best-effort Slack notification; the local case timeline is authoritative."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def dispatch(self, case: dict[str, Any], event: dict[str, str]) -> list[dict[str, str]]:
        outcomes = [
            {"connector": "local", "status": "recorded"},
            await self._slack(case, event),
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
