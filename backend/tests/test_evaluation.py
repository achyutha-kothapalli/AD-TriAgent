from app.evaluation import evaluate_scenarios
from app.models import FailureFamily, ReplayFrame, ScenarioRecord, VehicleState
from app.services.evidence import EvidenceExtractor


def test_evaluation_reports_routing_and_safety_boundary() -> None:
    scenario = ScenarioRecord(
        id="scenario-test",
        title="Evaluation test",
        source="metadrive_procedural",
        metadata={},
        event_frame=0,
        frames=[
            ReplayFrame(
                index=0,
                timestamp_s=0.0,
                ego=VehicleState(id="ego", x=0.0, y=0.0),
                metrics={
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
            )
        ],
        labels={"primary_failure": FailureFamily.PERCEPTION_LOCALIZATION.value},
    )

    report = evaluate_scenarios([scenario], EvidenceExtractor())

    assert report["routing"]["accuracy"] == 1.0
    assert report["safety_boundary"]["human_review_rate"] == 1.0
    assert report["safety_boundary"]["automatic_rule_activations"] == 0
