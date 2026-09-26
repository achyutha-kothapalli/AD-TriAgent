"""Offline evaluation for the synthetic disengagement corpus.

Run with: ``uv run python -m app.evaluation --input ../data/generated``.
The evaluator deliberately scores only deterministic routing. LLM prose is explanatory,
not a safety decision, and is measured separately through workflow telemetry.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.scenarios.repository import ScenarioRepository
from app.services.evidence import EvidenceExtractor


def evaluate_scenarios(scenarios: list, extractor: EvidenceExtractor | None = None) -> dict[str, Any]:
    extractor = extractor or EvidenceExtractor()
    started = time.perf_counter()
    correct = 0
    per_family: dict[str, dict[str, int]] = {}
    severities: dict[str, int] = {}

    for scenario in scenarios:
        result = extractor.extract(scenario)
        expected = scenario.labels.get("primary_failure")
        predicted = result.primary_family.value
        bucket = per_family.setdefault(expected or "unlabeled", {"cases": 0, "correct": 0})
        bucket["cases"] += 1
        if expected == predicted:
            correct += 1
            bucket["correct"] += 1
        severities[result.severity] = severities.get(result.severity, 0) + 1

    corpus_size = len(scenarios)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_size": corpus_size,
        "routing": {
            "correct": correct,
            "accuracy": round(correct / corpus_size, 4) if corpus_size else 0.0,
            "by_expected_family": {
                family: {
                    **stats,
                    "accuracy": round(stats["correct"] / stats["cases"], 4) if stats["cases"] else 0.0,
                }
                for family, stats in sorted(per_family.items())
            },
        },
        "safety_boundary": {
            "human_review_rate": 1.0 if corpus_size else 0.0,
            "automatic_rule_activations": 0,
            "scored_component": "deterministic evidence routing only",
        },
        "severity_distribution": severities,
        "evaluation_duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate deterministic triage routing on a corpus")
    parser.add_argument("--input", type=Path, required=True, help="Directory containing scenario-*.json")
    parser.add_argument("--output", type=Path, default=Path("data/runtime/evaluations/latest.json"))
    args = parser.parse_args()

    report = evaluate_scenarios(ScenarioRepository(args.input).all())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
