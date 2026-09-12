from __future__ import annotations

from uuid import uuid4

from app.models import RuleStatus
from app.services.evidence import EvidenceExtractor


class RuleMiner:
    def __init__(self, extractor: EvidenceExtractor) -> None:
        self.extractor = extractor

    def propose(self, case: dict, comment: dict) -> dict:
        triage = case["triage"]
        family = triage["primary_family"]
        metric_by_family = {
            "safety_conflict": "minimum TTC",
            "perception_localization": "minimum perception confidence",
            "prediction_interaction": "maximum prediction divergence",
            "planning_control": "maximum lane deviation",
            "odd_handover": "maximum system/handover risk",
        }
        signal = next(
            evidence
            for evidence in triage["evidence"]
            if evidence["metric"] == metric_by_family[family]
        )
        return {
            "id": f"rule-{uuid4().hex[:10]}",
            "version": 1,
            "status": RuleStatus.CANDIDATE.value,
            "family": family,
            "definition": (
                f"When a disengagement has {family.replace('_', ' ')} evidence and "
                f"{signal['metric']} is material, route it to the {family.replace('_', ' ')} review path."
            ),
            "provenance": {"case_id": case["id"], "comment_id": comment["id"], "author": comment["author"]},
        }

    def test(self, rule: dict, scenarios: list) -> dict:
        positives = 0
        true_positives = 0
        false_positives = 0
        for scenario in scenarios:
            predicted = self.extractor.extract(scenario).primary_family.value
            expected = scenario.labels.get("primary_failure")
            if predicted == rule["family"]:
                positives += 1
                if expected == rule["family"]:
                    true_positives += 1
                else:
                    false_positives += 1
        expected_count = sum(s.labels.get("primary_failure") == rule["family"] for s in scenarios)
        precision = true_positives / positives if positives else 0.0
        recall = true_positives / expected_count if expected_count else 0.0
        passed = precision >= 0.7 and recall >= 0.5 and true_positives >= 2
        return {
            "corpus_size": len(scenarios),
            "support": true_positives,
            "false_positives": false_positives,
            "precision": round(precision, 2),
            "recall": round(recall, 2),
            "passed": passed,
        }
