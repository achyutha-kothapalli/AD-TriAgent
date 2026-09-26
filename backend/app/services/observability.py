from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class WorkflowObserver:
    """Append-only, local telemetry for workflow behavior without case payloads or secrets."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        scenario_id: str,
        node: str,
        outcome: str,
        duration_ms: float,
        details: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "at": datetime.now(UTC).isoformat(),
            "scenario_id": scenario_id,
            "node": node,
            "outcome": outcome,
            "duration_ms": round(duration_ms, 2),
            "details": details or {},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")

    def summary(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"events": 0, "nodes": {}}
        node_stats: dict[str, dict[str, float | int]] = {}
        events = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            events += 1
            stats = node_stats.setdefault(
                event["node"], {"runs": 0, "errors": 0, "total_duration_ms": 0.0}
            )
            stats["runs"] += 1
            stats["errors"] += int(event["outcome"] == "error")
            stats["total_duration_ms"] += float(event["duration_ms"])
        return {
            "events": events,
            "nodes": {
                node: {
                    "runs": stats["runs"],
                    "errors": stats["errors"],
                    "average_duration_ms": round(stats["total_duration_ms"] / stats["runs"], 2),
                }
                for node, stats in node_stats.items()
            },
        }
