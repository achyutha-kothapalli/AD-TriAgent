# Retrieval-grounded investigation guidance

## Purpose

The RAG layer helps a reviewer decide **what to investigate next** after the
deterministic triage workflow has assigned a preliminary failure family. It does
not diagnose a root cause, determine compliance, change the triage route, or
approve a rule.

```text
case telemetry -> deterministic evidence and route -> allow-listed source-card retrieval
                                                    -> cited investigation directions
                                                    -> human expert review
```

This preserves the project’s safety boundary: numerical evidence and human
approval remain authoritative; an LLM may only explain the evidence and the
retrieved cards.

## Implementation

- `backend/app/knowledge/open_sources.json` is a versioned, allow-listed corpus.
  Every source has a URL, reuse note, limitation, failure-family tags, keywords,
  and project-authored investigation prompts.
- `backend/app/services/retrieval.py` keeps a dependency-free TF-IDF cosine
  retrieval baseline and adds an optional `QdrantInvestigationRetriever`. Qdrant
  embeds the same approved source cards with FastEmbed and applies hard filters
  for `approved=true`, corpus version, and the deterministically selected failure
  family.
- `retrieve_investigation_guidance` is an explicit LangGraph node. Its result is
  persisted in the case, logged through workflow observability, and visible in
  the UI.
- When an LLM is configured, `TriageNarrator` receives the source cards along
  with the evidence and must cite source IDs such as `[fhwa-ssam-surrogate-measures]`.
  When no LLM is configured, the source-linked investigation prompts are still
  shown deterministically.

`GET /api/investigation-sources` exposes corpus provenance and the active
retrieval backend. Retrieval needs no additional API key; `LLM_*` is only needed
for an optional natural-language summary. Set `RAG_BACKEND=qdrant` to activate
the vector backend. With a blank `QDRANT_URL`, Qdrant runs in local persisted
mode; set a URL and API key for Docker or Qdrant Cloud.

## Source and reuse policy

There is no meaningful category of “non-copyrighted documents” on the public
web: most documents are copyrighted even when freely downloadable. This POC
instead uses **licence-aware source cards**. It stores original summaries and
checklists, never copied PDFs, article text, or proprietary standards.

| Source card | Why it is included | Reuse handling |
| --- | --- | --- |
| NHTSA ADS safety elements | Review vocabulary for ODD, OEDR, fallback, and system safety | Official U.S. Government source; this repository retains only an original synopsis. |
| FHWA SSAM | Trajectory-based conflict measures including TTC and PET | Official U.S. Government source; this repository retains only an original synopsis. |
| PEGASUS Method | Scenario families, logical scenarios, and criticality-oriented investigation | Reference pointer only. The PEGASUS site was not confirmed as an open-content licence during this POC, so no source text or PDF is stored. |
| Sensors scenario-generation framework | Functional, logical, and concrete scenario decomposition | Open-access CC BY 4.0 article; attributed source card only. |
| NLOS critical-scenario paper | Occlusion-related edge-case investigation and multi-KPI reasoning | Open-access CC BY 4.0 article; attributed source card only. |

Before a production deployment, a legal/data owner should approve every source,
record its licence and version, and decide whether the full text may be indexed.
Do not ingest ISO standards, OEM documents, or incident records without explicit
rights, access controls, retention rules, and redaction.

## Evaluation

The synthetic labels evaluate deterministic routing, not RAG correctness. Add a
separate reviewed benchmark before making quality claims:

1. Create 25–50 anonymised cases with reviewer-written investigation questions.
2. Label which source cards are relevant for each case.
3. Measure Recall@k and reviewer relevance of retrieved cards.
4. Score citation correctness: every generated claim must be supported by a
   visible source card and case evidence.
5. Measure abstention quality when evidence or sources are insufficient.

The current corpus is intentionally small and curated for demonstration. Qdrant
is therefore a learning and scale-readiness backend, not a performance claim.
Evaluate its vector results against the local TF-IDF baseline before asserting an
improvement. For scale, combine lexical and dense retrieval, retain metadata
filters and citations, and evaluate the change against the same benchmark.
