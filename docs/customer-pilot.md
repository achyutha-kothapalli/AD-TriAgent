# Customer pilot pack

## Discovery questions

1. Which disengagements are currently reviewed, by whom, and what is the time-to-first-review?
2. Which telemetry fields are authoritative, how are they sampled, and what retention or access restrictions apply?
3. Which failure families, escalation paths, and rule-approval authority already exist?
4. What constitutes a useful pilot outcome: reduced review preparation time, improved routing agreement, or better rule provenance?

## Four-week pilot shape

| Week | Deliverable | Exit criterion |
| --- | --- | --- |
| 1 | Data discovery and profile mapping | Customer validates the canonical mapping and data-quality gaps. |
| 2 | Read-only replay and evidence packet | Reviewers confirm evidence is understandable and appropriately scoped. |
| 3 | Shadow triage and offline evaluation | Routing is compared with historical human labels; no production action is automated. |
| 4 | Rule-lifecycle workshop | Owner accepts/rejects candidate-rule process and decides go/no-go. |

## Success metrics

- Median time to prepare a review packet.
- Agreement between deterministic routing and adjudicated historical labels.
- Percentage of cases with complete evidence and provenance.
- Candidate-rule precision, recall, support, and owner approval rate.

The pilot is read-only and synthetic by default. Any customer-data use requires a
separate security, retention, and access review.
