# Deployment guide

## Local production-shaped demo

Generate the 30-case corpus once, then start the complete stack:

```powershell
cd backend
uv run python -m app.scenarios.generate --count 30 --output ../data/generated
cd ..
docker compose up --build
```

Open `http://localhost:5173`; the API health endpoint is at
`http://localhost:8000/health`. Docker mounts generated scenarios read-only and
keeps case state, the SQLite LangGraph checkpoint database, and telemetry in the
named `triage-runtime` volume.

## Optional vector retrieval

The default image starts with the dependency-free TF-IDF retrieval backend. To
enable the bundled Qdrant service, set `RAG_BACKEND=qdrant` and start Compose with
the `vector` profile:

```powershell
docker compose --profile vector up --build
```

The `qdrant-storage` volume retains the vector collection. For a managed Qdrant
deployment, omit the local service and set `QDRANT_URL` plus `QDRANT_API_KEY` in
the deployment secret manager. The vector corpus must remain allow-listed and
versioned; do not allow a runtime user to ingest arbitrary documents.

## Optional MLflow tracing

Set `MLFLOW_ENABLED=true` to write redacted workflow traces to the local SQLite
database `data/runtime/mlflow.db`. After processing at least one scenario, view
the local trace UI with:

```powershell
cd backend
uv run mlflow ui --backend-store-uri "sqlite:///../data/runtime/mlflow.db" --port 5000
```

Open `http://localhost:5000`. For a hosted MLflow deployment, configure
`MLFLOW_TRACKING_URI` through the deployment secret manager instead. The project
does not deploy an MLflow server itself. Keep `MLFLOW_LANGCHAIN_AUTOLOG=false`
for real or unreviewed data: the default manual spans contain safe metadata only,
whereas LangChain/LangGraph auto-tracing can capture prompts and responses.

## Hosted demo hand-off

Deploy the backend and frontend as separate services, set the frontend build-time
`VITE_API_URL` to the public backend URL, then set `CORS_ORIGINS` to the frontend
origin. Use a persistent volume for `data/runtime` and supply secrets only through
the hosting provider's secret manager. Keep `LLM_ENABLED=false` for a no-key demo.

The public demo must use only the supplied synthetic corpus. Do not upload real
vehicle telemetry or credentials to a shared demonstration deployment.

## Persistence boundary

The POC uses `AsyncSqliteSaver` for durable local checkpoints. SQLite is appropriate
for a single demo instance. Replace it with LangGraph's PostgreSQL saver before
running multiple backend workers or storing sensitive operational data.
