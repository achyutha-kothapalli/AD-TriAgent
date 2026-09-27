# Safety and governance

- This POC is decision support, not an autonomous driving control or release gate.
- The five triage families are routing hypotheses, not conclusive root-cause labels.
- Every agent explanation must reference extracted evidence and state uncertainty.
- Retrieved research or guidance may suggest a line of investigation only. It cannot
  establish root cause, compliance, or a release decision; citations and source
  limitations remain visible to the reviewer.
- Simulated personas are visibly marked and cannot approve rules.
- Candidate rules never activate from an LLM response or a single discussion comment.
- A candidate requires a regression test over the synthetic corpus and explicit system-owner approval.
- The graph records rule source case, author, test metrics, decision state, and approver.
