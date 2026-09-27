"""Optional, redacted MLflow tracing for the triage workflow.

The default trace contains workflow metadata only. Full LangChain auto-tracing is
opt-in because it can capture prompt and response content that may be sensitive in
a real vehicle-telemetry deployment.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import Settings


class MLflowTracer:
    """Create one case span with nested workflow-node spans when explicitly enabled."""

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.mlflow_enabled
        self._mlflow: Any | None = None
        if not self.enabled:
            return

        import mlflow

        tracking_uri = settings.mlflow_tracking_uri
        if not tracking_uri or not tracking_uri.strip():
            settings.runtime_path.mkdir(parents=True, exist_ok=True)
            tracking_uri = settings.mlflow_local_tracking_uri
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment)
        if settings.mlflow_langchain_autolog:
            mlflow.langchain.autolog(
                log_traces=True,
                log_models=False,
                log_input_examples=False,
                disable_for_unsupported_versions=True,
                silent=True,
            )
        self._mlflow = mlflow

    @contextmanager
    def workflow_span(self, scenario_id: str) -> Iterator[Any | None]:
        if self._mlflow is None:
            yield None
            return
        with self._mlflow.start_span(
            name="disengagement_triage",
            span_type="CHAIN",
            attributes={"workflow.engine": "langgraph", "scenario.id": scenario_id},
        ) as span:
            span.set_inputs({"scenario_id": scenario_id})
            yield span

    @contextmanager
    def node_span(self, node: str, state: dict[str, Any], details: dict[str, Any]) -> Iterator[None]:
        if self._mlflow is None:
            yield
            return
        with self._mlflow.start_span(
            name=f"triage.{node}",
            span_type="TOOL",
            attributes={"workflow.node": node, "scenario.id": state["scenario_id"]},
        ) as span:
            span.set_inputs({"scenario_id": state["scenario_id"], "node": node})
            try:
                yield
            except Exception as error:
                span.set_outputs({"outcome": "error", "error_type": type(error).__name__})
                raise
            else:
                span.set_outputs({"outcome": "ok", **self._safe_details(details)})

    def set_case_outcome(self, span: Any | None, case: dict[str, Any]) -> None:
        if span is None:
            return
        triage = case["triage"]
        span.set_outputs(
            {
                "case_id": case["id"],
                "primary_family": triage["primary_family"],
                "severity": triage["severity"],
                "guidance_status": triage.get("investigation_guidance", {}).get("status"),
                "review_status": case.get("human_review", {}).get("status"),
            }
        )

    @staticmethod
    def _safe_details(details: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
        return {
            key: value
            for key, value in details.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
