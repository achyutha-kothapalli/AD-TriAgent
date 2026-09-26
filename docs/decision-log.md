# Engineering decision log

| Decision | Why | Revisit when |
| --- | --- | --- |
| Deterministic routing decides; LLM explains | A safety review needs reproducible, inspectable evidence. | A validated, governed model-based classifier has been evaluated against approved data. |
| LangGraph workflow with explicit human gate | Makes state, review route, and hand-off visible rather than hiding them in chat. | Workflow requires branching/interrupts across multiple systems. |
| NetworkX + JSON provenance | Zero infrastructure for a 30-case POC; graph relationships remain inspectable. | Concurrent users, complex graph queries, or retention requirements need a managed datastore. |
| SQLite checkpoints locally | Durable restart recovery with no service dependency. | Multiple workers or sensitive production data require PostgreSQL and encryption/access control. |
| Profile-driven telemetry adapter | Customer integration is explicit and testable without coupling the product to one vendor. | A stable source system warrants a maintained API connector. |
