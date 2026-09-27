from app.config import Settings
from app.services.mlflow_tracing import MLflowTracer


def test_disabled_mlflow_tracer_is_a_noop() -> None:
    tracer = MLflowTracer(Settings(mlflow_enabled=False))

    with tracer.workflow_span("scenario-001") as span:
        assert span is None
        with tracer.node_span("extract_evidence", {"scenario_id": "scenario-001"}, {}):
            pass


def test_enabled_mlflow_tracer_writes_a_local_experiment(tmp_path) -> None:
    tracer = MLflowTracer(
        Settings(
            mlflow_enabled=True,
            runtime_dir=str(tmp_path / "runtime"),
            mlflow_experiment="triage-tracing-test",
        )
    )
    case = {
        "id": "case-scenario-001",
        "triage": {
            "primary_family": "safety_conflict",
            "severity": "P1",
            "investigation_guidance": {"status": "available"},
        },
        "human_review": {"status": "pending"},
    }

    with tracer.workflow_span("scenario-001") as span:
        assert span is not None
        with tracer.node_span(
            "retrieve_investigation_guidance",
            {"scenario_id": "scenario-001"},
            {"guidance_status": "available", "retrieved_sources": 3},
        ):
            pass
        tracer.set_case_outcome(span, case)

    assert (tmp_path / "runtime" / "mlflow.db").exists()
    assert tracer._mlflow is not None
    experiment = tracer._mlflow.get_experiment_by_name("triage-tracing-test")
    assert experiment is not None
    traces = tracer._mlflow.MlflowClient().search_traces(
        experiment_ids=[experiment.experiment_id],
        include_spans=True,
        flush=True,
    )
    assert [span.name for span in traces[0].data.spans] == [
        "disengagement_triage",
        "triage.retrieve_investigation_guidance",
    ]
