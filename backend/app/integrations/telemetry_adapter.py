"""Map a customer telemetry packet into the portable triage scenario contract.

The adapter intentionally accepts a profile-driven JSON mapping rather than a fixed
vendor SDK. It demonstrates the first FDE implementation step: establish a small,
testable boundary between an unfamiliar customer system and the product's canonical
event model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.models import ReplayFrame, ScenarioRecord, VehicleState


def load_profile(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def value_at(payload: dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _vehicle(payload: dict[str, Any], mapping: dict[str, str], fallback_id: str) -> VehicleState:
    return VehicleState(
        id=str(value_at(payload, mapping["id"], fallback_id)),
        kind=str(value_at(payload, mapping.get("kind", "kind"), "vehicle")),
        x=float(value_at(payload, mapping["x"], 0.0)),
        y=float(value_at(payload, mapping["y"], 0.0)),
        heading=float(value_at(payload, mapping.get("heading", "heading"), 0.0)),
        speed_mps=float(value_at(payload, mapping.get("speed_mps", "speed_mps"), 0.0)),
        color=str(value_at(payload, mapping.get("color", "color"), "#8bc7ff")),
    )


def adapt_telemetry(profile: dict[str, Any], payload: dict[str, Any]) -> ScenarioRecord:
    """Convert one customer event packet while retaining profile and source provenance."""
    event_mapping = profile["event"]
    frame_mapping = profile["frame"]
    raw_frames = value_at(payload, event_mapping["frames"])
    if not isinstance(raw_frames, list) or not raw_frames:
        raise ValueError("Customer packet must contain at least one mapped telemetry frame")

    frames: list[ReplayFrame] = []
    for index, raw_frame in enumerate(raw_frames):
        if not isinstance(raw_frame, dict):
            raise TypeError(f"Mapped frame {index} is not an object")
        raw_actors = value_at(raw_frame, frame_mapping.get("actors", "actors"), [])
        if not isinstance(raw_actors, list):
            raise TypeError(f"Mapped actors for frame {index} are not a list")
        metrics = {
            metric: float(value_at(raw_frame, source_path, 0.0))
            for metric, source_path in frame_mapping["metrics"].items()
        }
        frames.append(
            ReplayFrame(
                index=index,
                timestamp_s=float(value_at(raw_frame, frame_mapping["timestamp_s"], index / 10)),
                ego=_vehicle(value_at(raw_frame, frame_mapping["ego"], {}), frame_mapping["ego_vehicle"], "ego"),
                actors=[
                    _vehicle(actor, frame_mapping["actor_vehicle"], f"actor-{actor_index}")
                    for actor_index, actor in enumerate(raw_actors)
                    if isinstance(actor, dict)
                ],
                metrics=metrics,
                alerts=value_at(raw_frame, frame_mapping.get("alerts", "alerts"), []),
            )
        )

    labels: dict[str, Any] = {}
    label_path = event_mapping.get("primary_failure")
    if label_path:
        label = value_at(payload, label_path)
        if label:
            labels["primary_failure"] = label
    scenario_id = str(value_at(payload, event_mapping["id"]))
    return ScenarioRecord(
        id=f"scenario-{scenario_id}",
        title=str(value_at(payload, event_mapping["title"], f"Customer incident {scenario_id}")),
        source="customer_telemetry_adapter",
        metadata={
            "customer_profile": profile["id"],
            "source_system": profile["source_system"],
            "customer_metadata": value_at(payload, event_mapping.get("metadata", "metadata"), {}),
        },
        event_frame=int(value_at(payload, event_mapping["event_frame"], len(frames) // 2)),
        sampling_hz=int(profile.get("sampling_hz", 10)),
        frames=frames,
        labels=labels,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Adapt a customer telemetry packet for AD-TriAgent")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    scenario = adapt_telemetry(load_profile(args.profile), json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(scenario.model_dump_json(indent=2), encoding="utf-8")
    print(f"Wrote {scenario.id} using profile {scenario.metadata['customer_profile']}")


if __name__ == "__main__":
    main()
