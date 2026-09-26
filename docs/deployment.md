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
