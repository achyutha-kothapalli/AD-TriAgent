from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FailureFamily(str, Enum):
    SAFETY_CONFLICT = "safety_conflict"
    PERCEPTION_LOCALIZATION = "perception_localization"
    PREDICTION_INTERACTION = "prediction_interaction"
    PLANNING_CONTROL = "planning_control"
    ODD_HANDOVER = "odd_handover"


class RuleStatus(str, Enum):
    CANDIDATE = "candidate"
    TESTED = "tested"
    ACTIVE = "active"
    REJECTED = "rejected"


class CommentCreate(BaseModel):
    author: str = Field(min_length=2, max_length=80)
    role: str = Field(min_length=2, max_length=120)
    body: str = Field(min_length=4, max_length=4000)
    is_simulated_persona: bool = False


class RuleApproval(BaseModel):
    owner: str = Field(min_length=2, max_length=80)
    note: str = Field(default="", max_length=1000)


class CaseReview(BaseModel):
    reviewer: str = Field(min_length=2, max_length=80)
    reviewer_role: str = Field(min_length=2, max_length=120)
    action: Literal["approve", "request_more_evidence", "reject"]
    note: str = Field(default="", max_length=1000)


class VehicleState(BaseModel):
    id: str
    kind: str = "vehicle"
    x: float
    y: float
    heading: float = 0.0
    speed_mps: float = 0.0
    color: str = "#8bc7ff"


class ReplayFrame(BaseModel):
    index: int
    timestamp_s: float
    ego: VehicleState
    actors: list[VehicleState] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    alerts: list[str] = Field(default_factory=list)


class RoadLane(BaseModel):
    """Static lane geometry extracted from the MetaDrive procedural road network."""

    id: str
    polygon: list[list[float]]
    centerline: list[list[float]]
    width_m: float


class ScenarioRecord(BaseModel):
    id: str
    title: str
    source: str
    metadata: dict[str, Any]
    event_frame: int
    sampling_hz: int = 10
    frames: list[ReplayFrame]
    road_geometry: list[RoadLane] = Field(default_factory=list)
    labels: dict[str, Any] = Field(default_factory=dict)
