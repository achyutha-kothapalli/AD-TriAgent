# Ambiguous integration contract

The FastAPI case store is authoritative. Ambiguous and Slack are collaboration surfaces, never the
source of record for a triage label or an approved rule.

## Outbound events

`backend/app/collaboration/dispatcher.py` sends a portable case event when a case is triaged, an
expert comment creates a candidate rule, or the System Owner approves a rule. Before enabling it,
map `AMBIGUOUS_API_BASE_URL`, `AMBIGUOUS_API_TOKEN`, and `AMBIGUOUS_WORKSPACE_ID` to the actual
Ambiguous API or MCP contract supplied for the workspace. The current `/case-events` suffix is a
relay contract, not a claimed Ambiguous public endpoint.

## Inbound events

An Ambiguous-native integration or relay can send normalized events to:

`POST /webhooks/ambiguous`

It must calculate `HMAC-SHA256(raw request body, AMBIGUOUS_WEBHOOK_SECRET)` and provide it as
`X-Triage-Signature: sha256=<hex digest>`.

```json
{
  "event_id": "ambiguous-message-123",
  "case_id": "case-scenario-001",
  "kind": "expert_comment",
  "actor": "Perception coworker",
  "role": "Perception and localization expert",
  "message": "The evidence supports a sensor-confidence review."
}
```

`expert_comment` adds a provenance-bearing comment and mines a candidate rule. `task_update`
only updates the case timeline. Events are idempotent by `event_id`, and only the local System
Owner approval endpoint can activate a rule.

## Required Ambiguous information

- Workspace ID and an access token or OAuth/service-account method.
- Supported endpoints or MCP tools for case-thread creation, task assignment, and message posting.
- The inbound event mechanism: signed webhook preferred; otherwise a relay or polling contract.
- The real authorization scope, rate limits, and any data-retention restriction.
