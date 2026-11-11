# Retrieval-grounded investigation guidance

## Purpose and decision boundary

RAG helps a reviewer decide **what to investigate next** after deterministic
evidence extraction assigns a preliminary failure family. It does not diagnose a
root cause, determine compliance, change the route, or approve a rule.

```text
case telemetry -> deterministic evidence and route -> approved document retrieval
                                                    -> cited passages and questions
                                                    -> human expert review
```

Numerical evidence and human approval remain authoritative. An LLM may explain
only supplied evidence and retrieved material.

## Implemented corpus and chunking

`backend/app/knowledge/documents/` contains a versioned manifest and four
project-authored Markdown review guides:

- safety and trajectory conflict review;
- perception, localisation, and occlusion review;
- scenario, ODD, fallback, and handover review; and
- planning and control review.

The guides are original operational material. Their manifest preserves source
URLs, reuse basis, family tags, investigation prompts, limitations, and a corpus
version. They do not reproduce third-party PDFs, ISO standards, OEM documents, or
vehicle incident records.

`backend/app/services/retrieval.py` segments each guide into stable, overlapping
Markdown chunks. Every returned passage has a deterministic chunk ID, source
document ID, heading, checksum, and relevance score. The UI exposes the actual
retrieved passages alongside the source metadata, so a reviewer can inspect what
the RAG system used.

The dependency-free default uses lexical TF-IDF over chunks. The optional Qdrant
backend embeds **each chunk**, not one vector per document, and enforces hard
filters for approved status, corpus version, and deterministically selected
failure family.

## Ingestion policy

This repository intentionally does not scrape the web or ingest arbitrary PDFs at
runtime. Before adding a document, a data owner must establish:

1. the right to index and show the content;
2. its owner, version, source URL, and licence/reuse basis;
3. its allowed tenant/audience and retention policy; and
4. a reviewer's approval and the corpus-version change.

Add a document by placing an approved Markdown file beside `manifest.json`, adding
its metadata to the manifest, and bumping the corpus version. The next Qdrant
startup upserts version-tagged chunk vectors. A future production ingestion service
should additionally parse approved PDFs, record a durable source registry, and
remove superseded vectors under a transactional reindex job.

Do not ingest ISO standards, proprietary OEM material, customer telemetry, or
public pages with unconfirmed reuse rights without explicit approval and controls.

## Runtime behaviour

`retrieve_investigation_guidance` is an explicit LangGraph node. It persists its
result in the case, records safe observability metadata, and is visible in the
review room. If retrieval is unavailable, deterministic triage still runs and the
case remains in human review.

`GET /api/investigation-sources` returns corpus provenance plus document and chunk
counts. Retrieval needs no LLM API key. Configure `RAG_BACKEND=qdrant` to activate
the vector backend; a blank `QDRANT_URL` uses local persisted Qdrant mode.

## Evaluation plan

The synthetic scenario labels evaluate deterministic routing, not RAG quality.
Before making retrieval-quality claims, add a reviewed benchmark with:

1. anonymised or synthetic cases and reviewer-written investigation questions;
2. relevant-document and relevant-passage labels;
3. Recall@k, precision@k, and citation correctness;
4. an unsupported-claim/false-positive rate for generated prose; and
5. abstention quality when evidence or approved material is insufficient.

Evaluate Qdrant dense retrieval against the TF-IDF baseline on the same versioned
benchmark. Retain filters and citations even when adding hybrid retrieval or a
reranker.
