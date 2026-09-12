from __future__ import annotations

from dataclasses import asdict, dataclass

from app.models import FailureFamily, ScenarioRecord

FAMILY_LABELS = {
    FailureFamily.SAFETY_CONFLICT: "Safety-critical conflict",
    FailureFamily.PERCEPTION_LOCALIZATION: "Perception, localization, or map failure",
    FailureFamily.PREDICTION_INTERACTION: "Prediction or interaction failure",
    FailureFamily.PLANNING_CONTROL: "Planning, control, or compliance failure",
    FailureFamily.ODD_HANDOVER: "ODD, platform, or handover issue",
}


@dataclass(frozen=True)
class EvidenceResult:
    primary_family: FailureFamily
    severity: str
    confidence: float
    evidence: list[dict]
    contributing_factors: list[str]

    def as_dict(self) -> dict:
        result = asdict(self)
        result["primary_family"] = self.primary_family.value
        result["primary_family_label"] = FAMILY_LABELS[self.primary_family]
        return result


class EvidenceExtractor:
    """Deterministic signal extraction. An LLM explains, but never invents, these findings."""

    def extract(self, scenario: ScenarioRecord) -> EvidenceResult:
        window = scenario.frames[max(0, scenario.event_frame - 15) : scenario.event_frame + 11]
        metrics = self._metric_extremes(window)
        candidates = {
            FailureFamily.SAFETY_CONFLICT: max(0.0, (3.0 - metrics["min_ttc_s"]) / 3.0),
            # Strong, category-specific diagnostic signals establish the primary route.
            # TTC remains a contributing safety signal unless it is the sole dominant finding.
            FailureFamily.PERCEPTION_LOCALIZATION: 1.15
            * max(
                0.0,
                1.0 - metrics["min_perception_confidence"],
                metrics["max_localization_error_m"] / 2.5,
            ),
            FailureFamily.PREDICTION_INTERACTION: 1.15 * metrics["max_prediction_divergence"],
            FailureFamily.PLANNING_CONTROL: max(
                1.15 * metrics["max_lane_deviation_m"] / 1.5,
                1.15 * metrics["max_compliance_risk"],
            ),
            FailureFamily.ODD_HANDOVER: 1.2
            * max(metrics["max_system_health_risk"], metrics["max_handover_risk"]),
        }
        primary = max(candidates, key=candidates.get)
        score = min(1.0, candidates[primary])
        severity = "P0" if score >= 0.85 else "P1" if score >= 0.6 else "P2" if score >= 0.35 else "P3"

        evidence = [
            {"metric": "minimum TTC", "value": round(metrics["min_ttc_s"], 2), "unit": "s"},
            {
                "metric": "minimum perception confidence",
                "value": round(metrics["min_perception_confidence"], 2),
                "unit": "0-1",
            },
            {
                "metric": "maximum prediction divergence",
                "value": round(metrics["max_prediction_divergence"], 2),
                "unit": "0-1",
            },
            {
                "metric": "maximum lane deviation",
                "value": round(metrics["max_lane_deviation_m"], 2),
                "unit": "m",
            },
            {
                "metric": "maximum system/handover risk",
                "value": round(max(metrics["max_system_health_risk"], metrics["max_handover_risk"]), 2),
                "unit": "0-1",
            },
        ]
        ranked = sorted(candidates.items(), key=lambda item: item[1], reverse=True)
        factors = [FAMILY_LABELS[family] for family, value in ranked[1:3] if value >= 0.25]
        return EvidenceResult(primary, severity, round(0.55 + score * 0.4, 2), evidence, factors)

    @staticmethod
    def _metric_extremes(frames: list) -> dict[str, float]:
        def values(key: str, fallback: float) -> list[float]:
            return [float(frame.metrics.get(key, fallback)) for frame in frames]

        return {
            "min_ttc_s": min(values("ttc_s", 99.0)),
            "min_perception_confidence": min(values("perception_confidence", 1.0)),
            "max_localization_error_m": max(values("localization_error_m", 0.0)),
            "max_prediction_divergence": max(values("prediction_divergence", 0.0)),
            "max_lane_deviation_m": max(values("lane_deviation_m", 0.0)),
            "max_jerk_mps3": max(values("jerk_mps3", 0.0)),
            "max_compliance_risk": max(values("compliance_risk", 0.0)),
            "max_system_health_risk": max(values("system_health_risk", 0.0)),
            "max_handover_risk": max(values("handover_risk", 0.0)),
        }
