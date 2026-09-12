# Architecture

## Trust boundary

FastAPI owns scenario data, numerical evidence extraction, case state, and all outbound collaboration calls. The React browser receives replay data and approved public case state; it never receives LLM-provider or collaboration credentials. CopilotKit connects to the FastAPI AG-UI endpoint.

## Data flow

1. `app.scenarios.generate` drives a procedural `MetaDriveEnv` for each deterministic seed.
2. The generator writes a 150-frame, 10 Hz replay document with a disengagement anchor at frame 100.
3. The evidence extractor calculates a deterministic primary triage family from the event-centered window. Primary routing favours category-specific diagnostics over incidental simulation dynamics; TTC and jerk remain evidence and may be contributing safety signals.
4. The narrator may use the configured server-side LLM provider to explain that decision, but it may not overwrite numerical evidence or activate a rule.
5. Comments create provenance-linked candidate rules in the NetworkX graph.
6. A candidate is tested on the corpus, then only a system owner may activate a passing rule.

## Lightweight knowledge graph

`NetworkX.MultiDiGraph` persists at `data/runtime/rule_graph.json`. Nodes represent scenarios, cases, evidence, decisions, collaborators, comments, and rule versions. Edges preserve relationships such as `SUPPORTS`, `AUTHORED`, `PROPOSES`, and `DERIVED_FROM`.

The JSON artifact can be visualized in the frontend later or imported into a graph database if scale requires it. It is deliberately sufficient for a 30-case hackathon corpus without Docker or another managed service.

## Collaboration adapters

The local activity timeline is the source of truth. Slack and Ambiguous are best-effort mirrors, so a transient external outage cannot erase case provenance. Configure the adapters only with workspace-approved credentials.
