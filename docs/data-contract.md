# Customer telemetry data contract

AD-TriAgent accepts a canonical scenario document with an event identifier, title,
event-frame index, 10 Hz replay frames, ego and surrounding-actor state, numerical
metrics, alerts, and optional known labels. The internal models are defined in
`backend/app/models.py`.

The adapter profiles map a customer's nested event packet to this contract. Required
inputs are: an incident ID, a frame list, ego `x/y` position and speed, and the
metrics used by deterministic triage. Optional fields have conservative defaults and
must be surfaced in a pilot's data-quality report before relying on them.

Try the included mapping:

```powershell
cd backend
uv run python -m app.integrations.telemetry_adapter `
  --profile ../customer_profiles/urban-delivery-fleet.json `
  --input ../samples/customer_telemetry/urban-delivery-event.json `
  --output ../data/generated/scenario-urban-0001.json
```

The profiles are examples, not real OEM schemas. They show how a forward-deployed
engineer can make a customer-specific mapping explicit, versioned, reviewable, and
covered by tests.
