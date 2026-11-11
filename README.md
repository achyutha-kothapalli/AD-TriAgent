# Autonomous Driving Triage Agent

An evidence-first decision-support workflow for reviewing autonomous-driving
disengagements. Each case contains a locked **-10 s to +5 s** window around the
disengagement, expert collaboration, and versioned rule mining in a knowledge graph.

> This is a decision-support prototype using synthetic data. It is not a vehicle-control system and does not approve safety-critical operational decisions autonomously.

## What is included

- A generator that creates 30 synthetic scenario cases by driving procedural roads in MetaDrive.
- Five decision families: safety conflict, perception/localization/map, prediction/interaction, planning/control/compliance, and ODD/platform/handover.
- A LangGraph triage workflow: deterministic evidence, active-rule retrieval, retrieval-grounded investigation guidance, expert routing, constrained LLM explanation, and a persisted human-review gate.
- Two retrieval backends: a transparent local TF-IDF baseline and optional Qdrant dense-vector retrieval with source-family metadata filters.
- Reproducible corpus evaluation and per-node workflow telemetry, with no automatic rule activation.
- FastAPI endpoints for triage cases, comments, rule candidates, testing, and owner approval.
- A React case room with a browser-native top-down replay, evidence cards, collaboration timeline, and rule review panel.
- A lightweight NetworkX knowledge graph persisted as portable JSON, with no database service to operate.
- Optional Slack notifications for durable case updates.

## Architecture

```text
MetaDrive generator -> scenario JSON -> LangGraph triage workflow -> human-review gate
                                          |         |                    |
React case room <----- FastAPI <----- expert comments     |              v
Slack <-------------------- notification outbox ----------+       NetworkX rule graph
```

The browser uses its own Canvas replay of the MetaDrive-generated tracks, avoiding a graphical simulator dependency during a live demo. The source trajectories and scene metadata still originate from MetaDrive. An optional renderer script can be added later for recorded simulator video.

## Quick start

### Prerequisites

- Python 3.11 or newer, or [uv](https://docs.astral.sh/uv/)
- Node.js 20 or newer
- A MetaDrive-compatible Python environment (the backend resolves the official MetaDrive Git repository)

Copy `.env.example` to `.env`, then run the following from separate terminals. `uv` is the recommended path because it resolves the official MetaDrive repository and its simulator dependencies.

```powershell
uv sync --project backend --extra dev
cd backend
uv run python -m app.scenarios.generate --count 30 --output ../data/generated
uv run uvicorn app.main:app --reload --port 8000
```

On first generation, MetaDrive downloads its official simulator assets. Keep the generated `data/generated/` corpus local; it is deterministic and intentionally ignored by Git.

```powershell
cd frontend
pnpm install
pnpm run dev
```

Open `http://localhost:5173`. The API docs are at `http://localhost:8000/docs`.

### Docker demo

After generating the corpus, run `docker compose up --build` from the repository
root. This starts a production-shaped FastAPI backend and static frontend at the
same local URLs. See the [deployment guide](docs/deployment.md) for environment and
hosting details.

## Scenario corpus

The generator uses `MetaDriveEnv` to produce the road geometry and live vehicle tracks. It saves a compact browser replay format plus MetaDrive provenance (`seed`, map pattern, sampling rate, and generator version). Controlled fault overlays provide known labels and measurable telemetry patterns for the five triage families.

The committed repository contains no generated scenarios by default. This keeps the repository small and lets a demo corpus be reproduced with the deterministic generator command above.

## Optional notifications

The app runs in local-demo mode until credentials are provided.

- `SLACK_WEBHOOK_URL` mirrors important case events to a configured triage channel.
- `LLM_*` configures LangChain's server-side, OpenAI-compatible LLM provider. Leave `LLM_BASE_URL` blank for a direct OpenAI key.
- `RAG_*` configures the local, licence-aware chunked-document retriever. It requires
  no key; its cited passages suggest investigation directions but cannot change a
  decision.

Secrets belong only in `.env`; do not commit them.

See [RAG implementation and source policy](docs/rag.md) for the curated corpus,
licence safeguards, and evaluation plan.

### Optional Qdrant vector retrieval

The default `RAG_BACKEND=tfidf` works with no model download or service. To use
the vector backend locally, set `RAG_BACKEND=qdrant` and leave `QDRANT_URL` blank.
The first startup downloads the configured FastEmbed model and stores the local
Qdrant collection under `data/runtime/qdrant`.

To use a Docker Qdrant service instead, set `RAG_BACKEND=qdrant` and start:

```powershell
docker compose --profile vector up --build
```

Inside Compose, the backend uses `http://qdrant:6333`. For a managed instance,
set `QDRANT_URL` and `QDRANT_API_KEY` as deployment secrets. The active backend
and collection are exposed through `/api/investigation-sources`.

### Human decision boundary

The system accelerates investigation and preserves shared context; it never turns an AI suggestion into a safety decision by itself. LangGraph persists the case in `awaiting_human_review` after extracting evidence and assigning reviewers. The system owner approves rule activation only after a passing regression test, while every expert comment, candidate rule, test result, and approval is retained as case provenance in the NetworkX knowledge graph.

## Quality checks

```powershell
cd backend
uv run pytest
uv run ruff check .
```

```powershell
cd frontend
pnpm run check
pnpm run build
```

See [evaluation and observability](docs/evaluation.md) for the corpus-evaluation command and the metrics it reports.

### Optional MLflow tracing

Set `MLFLOW_ENABLED=true` to store local MLflow traces in the supported SQLite
database `data/runtime/mlflow.db` by default, or point `MLFLOW_TRACKING_URI` at a
managed MLflow server. Default traces record only case/node metadata, durations,
outcomes, and retrieval status. `MLFLOW_LANGCHAIN_AUTOLOG=true` additionally enables MLflow
LangChain/LangGraph auto-tracing and may capture prompts and responses, so use it
only with approved synthetic or properly redacted data.

## Customer-pilot readiness

The repository includes versioned example mappings for an urban delivery fleet and a
highway-pilot review feed. The [data contract](docs/data-contract.md),
[customer-pilot pack](docs/customer-pilot.md), and [engineering decision log](docs/decision-log.md)
show how to take this POC from discovery through a read-only pilot without claiming
that synthetic results are production safety validation.

## License

Copyright © 2026 Achyutha Kothapalli. This project is licensed under the
[Creative Commons Attribution-NonCommercial 4.0 International License](LICENSE)
(CC BY-NC 4.0). Commercial use is not permitted.

