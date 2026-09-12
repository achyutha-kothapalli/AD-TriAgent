from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat()


class CaseStore:
    """Tiny JSON case store. It is deliberately replaceable by a database later."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get(self, case_id: str) -> dict[str, Any] | None:
        return self._read().get(case_id)

    def all(self) -> list[dict[str, Any]]:
        return list(self._read().values())

    def upsert(self, case_id: str, value: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        data[case_id] = value
        self._write(data)
        return value

    def activity(self, case: dict[str, Any], kind: str, message: str, actor: str) -> None:
        case.setdefault("activity", []).append(
            {"id": f"activity-{len(case.get('activity', [])) + 1}", "at": now(), "kind": kind, "actor": actor, "message": message}
        )
