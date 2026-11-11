# Architecture

## Trust boundary

FastAPI owns scenario data, numerical evidence extraction, case state, and optional outbound Slack notifications. The React browser receives replay data and approved public case state; it never receives LLM-provider or notification credentials.

## Data flow

1. `app.scenarios.generate` drives a procedural `MetaDriveEnv` for each deterministic seed.
2. The generator writes a 150-frame, 10 Hz replay document with a disengagement anchor at frame 100.
3. A LangGraph workflow invokes the evidence extractor, retrieves active rules and licence-aware investigation documents, assigns the relevant expert route, then sets a case-level `awaiting_human_review` gate. Primary routing favours category-specific diagnostics over incidental simulation dynamics; TTC and jerk remain evidence and may be contributing safety signals.
4. The default local TF-IDF retriever, or an optional Qdrant dense-vector retriever with approved-document, corpus-version, and failure-family metadata filters, provides cited document passages from an allow-listed corpus of project-authored review guides. A LangChain OpenAI-compatible model may draft an explanation inside the workflow, but it may not overwrite numerical evidence, change the route, establish a root cause, or activate a rule.
5. Comments create provenance-linked candidate rules in the NetworkX graph.
6. A candidate is tested on the corpus, then only a system owner may activate a passing rule.

## Agent workflow

The production triage endpoint executes this checkpointed LangGraph path:

```text
extract evidence -> retrieve active rules -> retrieve investigation guidance -> assign expert route -> draft explanation
       -> awaiting human review -> persist case -> record graph provenance
```

The graph state is server-authoritative and keyed by scenario ID. The POC uses a
durable SQLite LangGraph checkpointer, which survives a local backend restart. A
production deployment should replace it with a PostgreSQL checkpointer before scaling
across workers or storing sensitive operational data.

See [retrieval-grounded investigation guidance](rag.md) for the source policy,
implementation, and evaluation plan.

## Lightweight knowledge graph

`NetworkX.MultiDiGraph` persists at `data/runtime/rule_graph.json`. Nodes represent scenarios, cases, evidence, decisions, collaborators, comments, and rule versions. Edges preserve relationships such as `SUPPORTS`, `AUTHORED`, `PROPOSES`, and `DERIVED_FROM`.

The JSON artifact can be visualized in the frontend later or imported into a graph database if scale requires it. It is deliberately sufficient for a 30-case hackathon corpus without Docker or another managed service.

## Notification adapter

The local activity timeline is the source of truth. Slack is a best-effort mirror, so a transient external outage cannot erase case provenance. Configure it only with an approved webhook URL.

## Optional MLflow tracing

`MLflowTracer` creates a redacted root span for a triage case and nested spans for
each LangGraph node. It records identifiers, node outcome, duration, retrieval
status, family, severity, and review status—not raw vehicle telemetry, comments,
or LLM messages. LangChain/LangGraph auto-tracing is separately opt-in because it
may capture prompts and responses. The existing JSONL observer remains the local
always-on POC telemetry source.
