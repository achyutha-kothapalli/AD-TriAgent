"""Generate a reproducible 30-case disengagement corpus from MetaDrive.

The procedural environment creates the road and vehicle motion. Fault overlays are
deliberately injected into telemetry around the anchor frame so the POC has known,
balanced triage cases without claiming that a simulator fault is a production fault.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from typing import Any

from app.models import FailureFamily, ReplayFrame, RoadLane, ScenarioRecord, VehicleState
from app.scenarios.repository import ScenarioRepository

SAMPLING_HZ = 10
FRAME_COUNT = 150
EVENT_FRAME = 100
PRE_ROLL_STEPS = 45
MIN_EGO_START_SPEED_MPS = 1.0
MIN_ACTOR_START_SPEED_MPS = 0.5
LANE_TOLERANCE_M = 0.25
PRE_ROLL_THROTTLE = 0.35
CRUISE_THROTTLE = 0.2
MAP_PATTERNS = ["S", "C", "X", "T", "O"]
FAMILIES = list(FailureFamily)


def _pair(value: Any) -> tuple[float, float]:
    """Read a simulator vector without binding the corpus to a physics backend."""
    try:
        return float(value[0]), float(value[1])
    except (TypeError, IndexError, KeyError):
        return 0.0, 0.0


def _speed_mps(vehicle: Any) -> float:
    speed_km_h = getattr(vehicle, "speed_km_h", None)
    if speed_km_h is not None:
        return float(speed_km_h) / 3.6
    vx, vy = _pair(getattr(vehicle, "velocity", (0.0, 0.0)))
    return math.hypot(vx, vy)


def _vehicle_state(vehicle: Any, fallback_id: str, color: str) -> VehicleState:
    x, y = _pair(getattr(vehicle, "position", (0.0, 0.0)))
    return VehicleState(
        id=str(getattr(vehicle, "id", fallback_id)),
        kind=str(getattr(vehicle, "vehicle_type", "vehicle")).lower(),
        x=round(x, 3),
        y=round(y, 3),
        heading=round(float(getattr(vehicle, "heading_theta", 0.0)), 3),
        speed_mps=round(_speed_mps(vehicle), 3),
        color=color,
    )


def _vehicle_is_on_lane(vehicle: Any) -> bool:
    """Validate a live simulator vehicle against its assigned MetaDrive lane."""
    lane = getattr(vehicle, "lane", None)
    position = getattr(vehicle, "position", None)
    if lane is None or position is None:
        return False
    try:
        _, lateral = lane.local_coordinates(position)
        return abs(float(lateral)) <= float(lane.width) / 2 + LANE_TOLERANCE_M
    except (AttributeError, TypeError, ValueError):
        return False


def _traffic_states(env: Any, ego: VehicleState, minimum_speed_mps: float = 0.0) -> list[VehicleState]:
    manager = getattr(getattr(env, "engine", None), "traffic_manager", None)
    vehicles = getattr(manager, "vehicles", {}) if manager else {}
    iterable = vehicles.values() if hasattr(vehicles, "values") else vehicles
    actors: list[VehicleState] = []
    for index, vehicle in enumerate(iterable):
        actor = _vehicle_state(vehicle, f"traffic-{index}", "#fbbf24")
        if actor.id == ego.id:
            continue
        if not _vehicle_is_on_lane(vehicle):
            continue
        if actor.speed_mps >= minimum_speed_mps and math.hypot(actor.x - ego.x, actor.y - ego.y) <= 90:
            actors.append(actor)
    return actors[:16]


def _road_geometry(env: Any) -> list[RoadLane]:
    """Export MetaDrive's lane polygons once; the browser only needs static road data."""
    road_network = env.engine.current_map.road_network
    lanes = road_network.get_all_lanes()
    geometry: list[RoadLane] = []
    for index, lane in enumerate(lanes):
        polygon = [[round(float(x), 3), round(float(y), 3)] for x, y in lane.polygon]
        centerline = [
            [round(float(x), 3), round(float(y), 3)]
            for x, y in lane.get_polyline(interval=1.0, lateral=0.0)
        ]
        if len(polygon) >= 3 and len(centerline) >= 2:
            geometry.append(
                RoadLane(
                    id=f"lane-{index}",
                    polygon=polygon,
                    centerline=centerline,
                    width_m=round(float(lane.width), 2),
                )
            )
    return geometry


def _base_metrics(ego: VehicleState, actors: list[VehicleState], previous_speed: float) -> dict[str, float]:
    ttc = 99.0
    for actor in actors:
        distance = math.hypot(actor.x - ego.x, actor.y - ego.y)
        closing_speed = max(0.1, ego.speed_mps - actor.speed_mps)
        if closing_speed > 0.3:
            ttc = min(ttc, max(0.0, (distance - 3.5) / closing_speed))
    jerk = abs(ego.speed_mps - previous_speed) * SAMPLING_HZ
    return {
        "ttc_s": round(ttc, 2),
        "perception_confidence": 0.98,
        "localization_error_m": 0.05,
        "prediction_divergence": 0.04,
        "lane_deviation_m": 0.05,
        "jerk_mps3": round(jerk, 2),
        "compliance_risk": 0.02,
        "system_health_risk": 0.01,
        "handover_risk": 0.02,
    }


def _fault_weight(frame_index: int) -> float:
    distance = abs(frame_index - EVENT_FRAME)
    return round(max(0.0, 1.0 - distance / 17.0), 3)


def _apply_fault_overlay(
    family: FailureFamily, frame: ReplayFrame, index: int, variant: int
) -> None:
    """Inject a measured, visible signal pattern centered on t=0."""
    weight = _fault_weight(index)
    if weight <= 0:
        return
    metrics = frame.metrics
    if family is FailureFamily.SAFETY_CONFLICT:
        metrics["ttc_s"] = round(min(metrics["ttc_s"], 4.2 - 3.35 * weight), 2)
        if weight > 0.55:
            frame.alerts.append("Unsafe closing gap detected")
    elif family is FailureFamily.PERCEPTION_LOCALIZATION:
        metrics["perception_confidence"] = round(max(0.08, 0.97 - 0.85 * weight), 2)
        metrics["localization_error_m"] = round(0.08 + 2.2 * weight, 2)
        if weight > 0.55:
            frame.alerts.append("Object-track confidence degraded")
    elif family is FailureFamily.PREDICTION_INTERACTION:
        metrics["prediction_divergence"] = round(0.04 + 0.88 * weight, 2)
        if weight > 0.55:
            frame.alerts.append("Predicted and observed actor path diverged")
    elif family is FailureFamily.PLANNING_CONTROL:
        metrics["lane_deviation_m"] = round(0.05 + 1.45 * weight, 2)
        metrics["jerk_mps3"] = round(max(metrics["jerk_mps3"], 2.0 + 7.2 * weight), 2)
        metrics["compliance_risk"] = round(0.03 + 0.79 * weight, 2)
        if weight > 0.55:
            frame.alerts.append("Lane/control policy risk detected")
    else:
        metrics["system_health_risk"] = round(0.02 + 0.85 * weight, 2)
        metrics["handover_risk"] = round(0.04 + 0.82 * weight, 2)
        if weight > 0.55:
            frame.alerts.append("Autonomy capability boundary reached")


def _wrap_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def _lane_following_steering(vehicle: Any) -> float:
    """Keep the ego vehicle centered on MetaDrive's currently assigned lane."""
    lane = getattr(vehicle, "lane", None)
    if lane is None:
        return 0.0
    try:
        longitudinal, lateral = lane.local_coordinates(vehicle.position)
        desired_heading = float(lane.heading_theta_at(longitudinal))
        heading_error = _wrap_angle(desired_heading - float(vehicle.heading_theta))
        # MetaDrive's positive lateral coordinate is to the vehicle's right of
        # travel, so the correction has the same sign as the heading correction.
        steering = 1.8 * heading_error + 0.28 * float(lateral)
        return round(max(-1.0, min(1.0, steering)), 3)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _action_for(family: FailureFamily, frame_index: int, ego_vehicle: Any) -> list[float]:
    """Retain mostly natural MetaDrive traffic while varying ego behavior slightly."""
    # Fault categories are represented by telemetry overlays, not an unsafe steering
    # injection. This keeps the recorded ego vehicle on its live MetaDrive lane.
    if family is FailureFamily.PLANNING_CONTROL and EVENT_FRAME - 6 <= frame_index <= EVENT_FRAME + 5:
        return [_lane_following_steering(ego_vehicle), 0.1]
    if family is FailureFamily.SAFETY_CONFLICT and EVENT_FRAME - 5 <= frame_index <= EVENT_FRAME + 4:
        return [_lane_following_steering(ego_vehicle), -0.15]
    return [_lane_following_steering(ego_vehicle), CRUISE_THROTTLE]


def _unpack_step(result: Any) -> tuple[bool, bool]:
    if len(result) == 5:
        _, _, terminated, truncated, _ = result
        return bool(terminated), bool(truncated)
    _, _, done, _ = result
    return bool(done), False


def _generate_one(case_number: int, output: Path) -> ScenarioRecord:
    matplotlib_config = output.parent / ".mplconfig"
    matplotlib_config.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_config))
    try:
        from metadrive.envs import MetaDriveEnv
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "MetaDrive is required. Install backend dependencies before generating the corpus."
        ) from error

    family = FAMILIES[(case_number - 1) % len(FAMILIES)]
    variant = (case_number - 1) // len(FAMILIES)
    seed = 2300 + case_number
    map_pattern = MAP_PATTERNS[(case_number - 1) % len(MAP_PATTERNS)]
    config = {
        "use_render": False,
        "map": map_pattern,
        "traffic_density": 0.18 + (variant % 3) * 0.05,
        "num_scenarios": 1,
        "start_seed": seed,
        "horizon": FRAME_COUNT + PRE_ROLL_STEPS + 50,
        "crash_vehicle_done": False,
        "out_of_road_done": False,
        "out_of_route_done": False,
    }
    env = MetaDriveEnv(config)
    frames: list[ReplayFrame] = []
    try:
        env.reset(seed=seed)
        road_geometry = _road_geometry(env)
        for _ in range(PRE_ROLL_STEPS):
            terminated, truncated = _unpack_step(
                env.step([_lane_following_steering(env.agent), PRE_ROLL_THROTTLE])
            )
            if terminated or truncated:
                raise RuntimeError(f"MetaDrive ended during pre-roll for scenario {case_number}")

        ego_vehicle = getattr(env, "agent", None)
        if ego_vehicle is None:
            agents = getattr(env, "agents", {})
            ego_vehicle = next(iter(agents.values()))
        initial_ego = _vehicle_state(ego_vehicle, "ego", "#5eead4")
        initial_actors = _traffic_states(env, initial_ego, MIN_ACTOR_START_SPEED_MPS)
        if not _vehicle_is_on_lane(ego_vehicle):
            raise RuntimeError(f"MetaDrive ego is not on a lane at scenario {case_number} start")
        if initial_ego.speed_mps < MIN_EGO_START_SPEED_MPS:
            raise RuntimeError(f"MetaDrive ego did not reach the initial speed threshold for scenario {case_number}")
        if not initial_actors:
            raise RuntimeError(f"MetaDrive produced no moving traffic for scenario {case_number}")

        previous_speed = initial_ego.speed_mps
        for index in range(FRAME_COUNT):
            ego_vehicle = getattr(env, "agent", None)
            if ego_vehicle is None:
                agents = getattr(env, "agents", {})
                ego_vehicle = next(iter(agents.values()))
            if not _vehicle_is_on_lane(ego_vehicle):
                raise RuntimeError(f"MetaDrive ego left its lane in scenario {case_number} at frame {index}")
            ego = _vehicle_state(ego_vehicle, "ego", "#5eead4")
            actors = _traffic_states(
                env,
                ego,
                MIN_ACTOR_START_SPEED_MPS if index == 0 else 0.0,
            )
            frame = ReplayFrame(
                index=index,
                timestamp_s=round(index / SAMPLING_HZ - 10.0, 2),
                ego=ego,
                actors=actors,
                metrics=_base_metrics(ego, actors, previous_speed),
            )
            _apply_fault_overlay(family, frame, index, variant)
            frames.append(frame)
            previous_speed = ego.speed_mps
            terminated, truncated = _unpack_step(env.step(_action_for(family, index, ego_vehicle)))
            if terminated or truncated:
                # Completion is a valid simulator outcome. Continue the fixed review window
                # with the last real state rather than fabricating another simulator segment.
                break
    finally:
        env.close()

    if not frames:
        raise RuntimeError(f"MetaDrive returned no frames for scenario {case_number}")
    while len(frames) < FRAME_COUNT:
        clone = frames[-1].model_copy(deep=True)
        clone.index = len(frames)
        clone.timestamp_s = round(clone.index / SAMPLING_HZ - 10.0, 2)
        clone.alerts = ["Simulator episode ended before review window completed"]
        frames.append(clone)

    title = f"{family.value.replace('_', ' ').title()} · synthetic case {case_number:02d}"
    record = ScenarioRecord(
        id=f"scenario-{case_number:03d}",
        title=title,
        source="metadrive_procedural",
        event_frame=EVENT_FRAME,
        metadata={
            "generator": "MetaDriveEnv",
            "seed": seed,
            "map_pattern": map_pattern,
            "review_window_seconds": [-10, 5],
            "pre_roll_seconds": PRE_ROLL_STEPS / SAMPLING_HZ,
            "initial_ego_speed_mps": initial_ego.speed_mps,
            "initial_moving_non_ego_count": len(initial_actors),
            "lane_validated": True,
            "disengagement_initiator": "system" if case_number % 3 else "user",
            "overlay": "controlled telemetry fault overlay",
        },
        frames=frames,
        road_geometry=road_geometry,
        labels={"primary_failure": family.value, "variant": variant + 1},
    )
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{record.id}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return record


def generate(count: int, output: Path) -> None:
    if count < len(FAMILIES):
        raise ValueError(f"Generate at least {len(FAMILIES)} cases to cover each failure family.")
    for case_number in range(1, count + 1):
        record = _generate_one(case_number, output)
        print(f"generated {record.id}: {record.labels['primary_failure']}")
    ScenarioRepository(output).write_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MetaDrive triage cases")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("../data/generated"))
    args = parser.parse_args()
    generate(args.count, args.output.resolve())


if __name__ == "__main__":
    main()
