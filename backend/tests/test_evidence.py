from app.models import FailureFamily, ReplayFrame, ScenarioRecord, VehicleState
from app.services.evidence import EvidenceExtractor
from app.services.rules import RuleMiner


def scenario_with(metrics: dict[str, float], expected: FailureFamily) -> ScenarioRecord:
    frame = ReplayFrame(
        index=0,
        timestamp_s=0.0,
        ego=VehicleState(id="ego", x=0.0, y=0.0),
        metrics=metrics,
    )
    return ScenarioRecord(
        id="scenario-test",
        title="test",
        source="metadrive_procedural",
        metadata={},
        event_frame=0,
        frames=[frame],
        labels={"primary_failure": expected.value},
    )


def test_perception_signal_routes_to_perception_family() -> None:
    scenario = scenario_with(
        {
            "ttc_s": 10.0,
            "perception_confidence": 0.1,
            "localization_error_m": 2.1,
            "prediction_divergence": 0.1,
            "lane_deviation_m": 0.0,
            "jerk_mps3": 0.0,
            "compliance_risk": 0.0,
            "system_health_risk": 0.0,
            "handover_risk": 0.0,
        },
        FailureFamily.PERCEPTION_LOCALIZATION,
    )
    result = EvidenceExtractor().extract(scenario)
    assert result.primary_family is FailureFamily.PERCEPTION_LOCALIZATION
    assert result.severity in {"P0", "P1"}


def test_rule_requires_supporting_cases_before_it_passes() -> None:
    extractor = EvidenceExtractor()
    candidate = {
        "id": "rule-1",
        "family": FailureFamily.SAFETY_CONFLICT.value,
        "definition": "test",
    }
    low_support = [
        scenario_with(
            {
                "ttc_s": 0.8,
                "perception_confidence": 1.0,
                "localization_error_m": 0.0,
                "prediction_divergence": 0.0,
                "lane_deviation_m": 0.0,
                "jerk_mps3": 0.0,
                "compliance_risk": 0.0,
                "system_health_risk": 0.0,
                "handover_risk": 0.0,
            },
            FailureFamily.SAFETY_CONFLICT,
        )
    ]
    assert RuleMiner(extractor).test(candidate, low_support)["passed"] is False
