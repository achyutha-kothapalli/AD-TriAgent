# Evaluation and observability

The evaluation scope is intentionally narrow: it measures deterministic
failure-family routing on the labeled synthetic MetaDrive corpus. It does not score
LLM prose as a safety decision, because the LLM can only explain supplied evidence.

Run the evaluation after generating the corpus:

```powershell
cd backend
uv run python -m app.evaluation --input ../data/generated --output ../data/runtime/evaluations/latest.json
```

The report contains corpus size, overall and per-family routing accuracy, severity
distribution, elapsed time, and explicit safety-boundary metrics. A healthy report
always shows zero automatic rule activations and a 100% human-review rate.

Every LangGraph node also appends a compact event to
`data/runtime/workflow_events.jsonl`: scenario ID, node name, success/error outcome,
duration, and non-sensitive metadata such as LLM/fallback source. Query the local
summary at `GET /api/observability/summary`.

When `MLFLOW_ENABLED=true`, the same workflow has an optional MLflow trace view.
By default it stores redacted case and node metadata in the SQLite database
`data/runtime/mlflow.db`; set
`MLFLOW_TRACKING_URI` to use a managed server. Keep
`MLFLOW_LANGCHAIN_AUTOLOG=false` unless prompt/response capture has been approved.

This is deliberately a POC-scale observability layer. A production deployment would
export the same events to an approved telemetry service and apply retention/access
controls appropriate for vehicle data.
