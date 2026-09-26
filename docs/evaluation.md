# Evaluation and observability

The portfolio claim is intentionally narrow: the evaluator measures deterministic
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

This is deliberately a POC-scale observability layer. A production deployment would
export the same events to an approved telemetry service and apply retention/access
controls appropriate for vehicle data.
