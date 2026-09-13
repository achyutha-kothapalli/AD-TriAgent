# Autonomous Driving Triage Agent

A hackathon POC for reviewing autonomous-driving disengagements. Each case contains a locked **-10 s to +5 s** window around the disengagement, an evidence-first triage decision, expert collaboration, and versioned rule mining in a knowledge graph.

> This is a decision-support prototype using synthetic data. It is not a vehicle-control system and does not approve safety-critical operational decisions autonomously.

## What is included

- A generator that creates 30 synthetic scenario cases by driving procedural roads in MetaDrive.
- Five decision families: safety conflict, perception/localization/map, prediction/interaction, planning/control/compliance, and ODD/platform/handover.
- FastAPI endpoints for triage cases, comments, rule candidates, testing, and owner approval.
- A React/CopilotKit case room with a browser-native top-down replay, evidence cards, collaboration timeline, and rule review panel.
- A lightweight NetworkX knowledge graph persisted as portable JSON, with no database service to operate.
- Slack and Ambiguous integration seams; when credentials are supplied, the case service mirrors durable case updates to those collaboration systems.

## Architecture

```text
MetaDrive generator -> scenario JSON -> evidence extractor -> triage orchestrator
                                                          |        |
React + CopilotKit <- FastAPI + AG-UI <- expert comments  |        v
Ambiguous + Slack <---------------- case event outbox ----+  NetworkX rule graph
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

## Scenario corpus

The generator uses `MetaDriveEnv` to produce the road geometry and live vehicle tracks. It saves a compact browser replay format plus MetaDrive provenance (`seed`, map pattern, sampling rate, and generator version). Controlled fault overlays provide known labels and measurable telemetry patterns for the five triage families.

The committed repository contains no generated scenarios by default. This keeps the repository small and lets a demo corpus be reproduced with the deterministic generator command above.

## Collaboration connectors

The app runs in local-demo mode until credentials are provided.

- `SLACK_WEBHOOK_URL` mirrors important case events to a configured triage channel.
- `LLM_*` configures a server-side OpenAI-compatible LLM provider. Leave `LLM_BASE_URL` blank for a direct OpenAI key.
- `AMBIGUOUS_*` enables the Ambiguous adapter. The adapter intentionally sends only a portable case record; map its endpoint fields in `backend/app/collaboration/dispatcher.py` to the authenticated Ambiguous workspace API or MCP transport available to your workspace.

Secrets belong only in `.env`; do not commit them.

## AI collaboration surfaces

### CopilotKit: the evidence copilot inside a triage case

CopilotKit makes the AI available where a reviewer is already working: the case room. The React client shares the selected case, replay time, and key metrics with the FastAPI/LangGraph agent through AG-UI. The backend then reloads the authoritative case record before the model is asked to help, so the browser is not the source of truth.

For a reviewer, this turns the case room into a conversational investigation surface. They can ask why a case was routed to a failure family, request a concise evidence summary, identify missing evidence, or turn an expert observation into a draft rule. The agent can explain and propose; it does not approve a triage label, activate a rule, or make a vehicle decision. Those actions remain with the system owner.

The direct AG-UI connection in this POC keeps the demo small. A production deployment can place the same agent behind CopilotKit's server runtime and application authentication.

### Ambiguous AI: the persistent AI coworker across specialists

Ambiguous AI provides the collaboration layer beyond a single browser session. The triage agent can participate as a persistent coworker alongside the system owner and specialists in perception, prediction, planning, safety, and operations. It gives the team a shared place to discuss a case, request a specialist review, and carry the investigation forward between case-room visits.

The integration is event-based. Durable case events—triage completed, expert comment added, rule candidate created, test completed, and owner decision—are emitted as portable case records. Incoming expert feedback is normalized back into the case timeline with its author and timestamp. That feedback is then available to the rule-mining flow and remains traceable to the scenario that motivated it.

For a live Ambiguous workspace, configure the `AMBIGUOUS_*` values in `.env` and map the outbound event contract in `backend/app/collaboration/dispatcher.py` to the workspace's authenticated API or MCP transport. Keep the webhook signing secret private. Slack can mirror the most important events for teams that prefer a channel-based notification trail.

### Human decision boundary

The system accelerates investigation and preserves shared context; it never turns an AI suggestion into a safety decision by itself. The system owner approves final triage outcomes and rule activation, while every expert comment, candidate rule, test result, and approval is retained as case provenance in the NetworkX knowledge graph.

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

## License

Copyright © 2026 Achyutha Kothapalli. This project is licensed under the
[Creative Commons Attribution-NonCommercial 4.0 International License](LICENSE)
(CC BY-NC 4.0). Commercial use is not permitted.

## Demo script

1. Open a queued disengagement and replay the 15-second window.
2. Inspect the evidence and ask the triage agent why the case was routed.
3. Add an expert comment that changes the interpretation.
4. Watch a rule candidate appear, run its regression test, then approve it as the system owner.
5. Open a related later scenario and show the now-active rule cited in the triage result.
