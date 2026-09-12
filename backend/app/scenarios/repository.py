from __future__ import annotations

import json
from pathlib import Path

from app.models import ScenarioRecord


class ScenarioRepository:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def all(self) -> list[ScenarioRecord]:
        if not self.directory.exists():
            return []
        scenarios: list[ScenarioRecord] = []
        for path in sorted(self.directory.glob("scenario-*.json")):
            scenarios.append(ScenarioRecord.model_validate_json(path.read_text(encoding="utf-8")))
        return scenarios

    def get(self, scenario_id: str) -> ScenarioRecord | None:
        path = self.directory / f"{scenario_id}.json"
        if not path.exists():
            return None
        return ScenarioRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def public_summary(self, scenario: ScenarioRecord) -> dict:
        return {
            "id": scenario.id,
            "title": scenario.title,
            "source": scenario.source,
            "event_frame": scenario.event_frame,
            "metadata": scenario.metadata,
        }

    def write_index(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        index = [self.public_summary(scenario) for scenario in self.all()]
        (self.directory / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
