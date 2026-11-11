"""Licence-aware document retrieval for evidence-first triage.

The RAG corpus is deliberately small and versioned. It contains project-authored
review guides with explicit source links and reuse notes, rather than copied
standards, OEM material, or ungoverned web pages.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from app.config import Settings

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {"and", "for", "from", "into", "the", "this", "with"}
CHUNK_WORDS = 110
CHUNK_OVERLAP_WORDS = 24

FAMILY_QUERY_TERMS = {
    "safety_conflict": "time to collision trajectory interaction conflict evasive action",
    "perception_localization": "perception confidence localization map occlusion visibility object detection",
    "prediction_interaction": "actor motion prediction trajectory interaction criticality",
    "planning_control": "lane deviation control maneuver trajectory compliance",
    "odd_handover": "operational design domain fallback handover system health takeover",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(value.lower())
        if len(token) > 1 and token not in STOP_WORDS
    }


@dataclass(frozen=True)
class KnowledgeDocument:
    """An approved, project-authored guide with traceable original references."""

    id: str
    title: str
    publisher: str
    url: str
    reuse_basis: str
    families: list[str]
    keywords: list[str]
    summary: str
    investigation_prompts: list[str]
    limitations: str
    path: Path

    @classmethod
    def from_dict(cls, raw: dict[str, Any], corpus_directory: Path) -> KnowledgeDocument:
        return cls(
            id=str(raw["id"]),
            title=str(raw["title"]),
            publisher=str(raw["publisher"]),
            url=str(raw["url"]),
            reuse_basis=str(raw["reuse_basis"]),
            families=[str(value) for value in raw["families"]],
            keywords=[str(value) for value in raw["keywords"]],
            summary=str(raw["summary"]),
            investigation_prompts=[str(value) for value in raw["investigation_prompts"]],
            limitations=str(raw["limitations"]),
            path=corpus_directory / str(raw["path"]),
        )

    def citation(self, score: float) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "publisher": self.publisher,
            "url": self.url,
            "summary": self.summary,
            "reuse_basis": self.reuse_basis,
            "limitations": self.limitations,
            "relevance_score": round(score, 3),
        }


@dataclass(frozen=True)
class KnowledgeChunk:
    """A citable, stable segment of one approved corpus document."""

    id: str
    document: KnowledgeDocument
    heading: str
    text: str
    ordinal: int
    checksum: str

    def searchable_text(self) -> str:
        return " ".join(
            [
                self.document.title,
                self.document.publisher,
                *self.document.families,
                *self.document.keywords,
                self.document.summary,
                self.heading,
                self.text,
            ]
        )

    def passage(self, score: float) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document.id,
            "heading": self.heading,
            "text": self.text,
            "checksum": self.checksum,
            "relevance_score": round(score, 3),
        }


class GuidanceRetriever(Protocol):
    def catalog(self) -> dict[str, Any]: ...

    def retrieve(self, triage: dict[str, Any]) -> dict[str, Any]: ...

    def close(self) -> None: ...


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _markdown_sections(markdown: str) -> list[tuple[str, str]]:
    """Extract prose sections without adding a Markdown parser dependency."""

    heading = "Overview"
    sections: list[tuple[str, str]] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            text = " ".join(paragraph).strip()
            if text:
                sections.append((heading, text))
            paragraph.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip() or "Overview"
        elif not line:
            flush()
        elif not line.startswith("<!--"):
            paragraph.append(line)
    flush()
    return sections


def _chunk_document(document: KnowledgeDocument) -> list[KnowledgeChunk]:
    if not document.path.is_file():
        raise ValueError(f"Approved RAG document is missing: {document.path}")
    chunks: list[KnowledgeChunk] = []
    ordinal = 1
    for heading, section in _markdown_sections(document.path.read_text(encoding="utf-8")):
        words = section.split()
        for start in range(0, len(words), CHUNK_WORDS - CHUNK_OVERLAP_WORDS):
            text = " ".join(words[start : start + CHUNK_WORDS]).strip()
            if not text:
                continue
            checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            chunks.append(
                KnowledgeChunk(
                    id=f"{document.id}:chunk-{ordinal:03d}",
                    document=document,
                    heading=heading,
                    text=text,
                    ordinal=ordinal,
                    checksum=checksum,
                )
            )
            ordinal += 1
            if start + CHUNK_WORDS >= len(words):
                break
    if not chunks:
        raise ValueError(f"Approved RAG document has no indexable prose: {document.path}")
    return chunks


class InvestigationRetriever:
    """Deterministic TF-IDF retrieval over approved, chunked Markdown documents."""

    def __init__(self, corpus_path: Path, enabled: bool = True, top_k: int = 3) -> None:
        self.enabled = enabled
        self.top_k = top_k
        raw = json.loads(corpus_path.read_text(encoding="utf-8"))
        self.corpus_id = str(raw["corpus_id"])
        self.version = str(raw["version"])
        self.content_policy = str(raw["content_policy"])
        self.documents = [KnowledgeDocument.from_dict(item, corpus_path.parent) for item in raw["documents"]]
        if not self.documents:
            raise ValueError("The investigation guidance corpus is empty")
        self.sources = self.documents
        self.chunks = [chunk for document in self.documents for chunk in _chunk_document(document)]
        self._chunk_tokens = {chunk.id: _tokens(chunk.searchable_text()) for chunk in self.chunks}
        self._document_frequency = self._document_frequencies()

    def catalog(self) -> dict[str, Any]:
        return {
            "backend": "tfidf",
            "corpus_id": self.corpus_id,
            "version": self.version,
            "content_policy": self.content_policy,
            "document_count": len(self.documents),
            "chunk_count": len(self.chunks),
            "sources": [document.citation(score=0.0) for document in self.documents],
        }

    def retrieve(self, triage: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return self._empty_result("disabled", "local_tfidf_chunked_documents_with_family_metadata")

        family = str(triage["primary_family"])
        query = self._query_for(triage)
        eligible = [chunk for chunk in self.chunks if family in chunk.document.families] or self.chunks
        ranked = sorted(
            ((self._score(query, chunk, family), chunk) for chunk in eligible),
            key=lambda item: item[0],
            reverse=True,
        )[: self.top_k]
        return self._guidance_from_ranked(
            ranked,
            query=query,
            retrieval_method="local_tfidf_chunked_documents_with_family_metadata",
        )

    def close(self) -> None:
        """Keep a common lifecycle interface with networked retrieval backends."""

    def _empty_result(self, status: str, retrieval_method: str) -> dict[str, Any]:
        return {
            "status": status,
            "retrieval_method": retrieval_method,
            "decision_boundary": "No retrieved guidance is used for routing or approval.",
            "directions": [],
            "sources": [],
            "retrieved_passages": [],
        }

    def _guidance_from_ranked(
        self,
        ranked: list[tuple[float, KnowledgeChunk]],
        *,
        query: set[str],
        retrieval_method: str,
    ) -> dict[str, Any]:
        results = [(score, chunk) for score, chunk in ranked if score > 0]
        source_scores: dict[str, float] = {}
        source_by_id: dict[str, KnowledgeDocument] = {}
        directions: list[dict[str, str]] = []
        directed_sources: set[str] = set()
        for score, chunk in results:
            document = chunk.document
            source_scores[document.id] = max(score, source_scores.get(document.id, 0.0))
            source_by_id[document.id] = document
            if document.id not in directed_sources and document.investigation_prompts:
                directions.append(
                    {
                        "text": document.investigation_prompts[0],
                        "source_id": document.id,
                        "passage_id": chunk.id,
                    }
                )
                directed_sources.add(document.id)
        return {
            "status": "available" if results else "no_match",
            "retrieval_method": retrieval_method,
            "corpus_id": self.corpus_id,
            "corpus_version": self.version,
            "query_terms": sorted(query),
            "decision_boundary": (
                "Retrieved material suggests investigation directions only; it cannot establish a "
                "root cause, compliance status, routing decision, or rule approval."
            ),
            "directions": directions,
            "sources": [
                source_by_id[document_id].citation(source_scores[document_id])
                for document_id in source_scores
            ],
            "retrieved_passages": [chunk.passage(score) for score, chunk in results],
        }

    def _document_frequencies(self) -> dict[str, int]:
        frequencies: dict[str, int] = {}
        for tokens in self._chunk_tokens.values():
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1
        return frequencies

    def _query_for(self, triage: dict[str, Any]) -> set[str]:
        family = str(triage["primary_family"])
        terms = [
            family.replace("_", " "),
            str(triage.get("primary_family_label", "")),
            FAMILY_QUERY_TERMS.get(family, ""),
            " ".join(str(factor) for factor in triage.get("contributing_factors", [])),
            " ".join(str(item.get("metric", "")) for item in triage.get("evidence", [])),
        ]
        return _tokens(" ".join(terms))

    def _score(self, query: set[str], chunk: KnowledgeChunk, family: str) -> float:
        document = self._chunk_tokens[chunk.id]
        shared = query & document
        if not shared:
            return 0.05 if family in chunk.document.families else 0.0
        document_count = len(self.chunks)

        def weight(token: str) -> float:
            return math.log((document_count + 1) / (self._document_frequency.get(token, 0) + 1)) + 1

        numerator = sum(weight(token) ** 2 for token in shared)
        query_norm = math.sqrt(sum(weight(token) ** 2 for token in query))
        document_norm = math.sqrt(sum(weight(token) ** 2 for token in document))
        cosine = numerator / (query_norm * document_norm) if query_norm and document_norm else 0.0
        return cosine + (0.18 if family in chunk.document.families else 0.0)


class FastEmbedEmbedder:
    """Local embedding provider; the selected model downloads on first Qdrant use."""

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(value) for value in vector] for vector in self.model.embed(texts)]


class QdrantInvestigationRetriever:
    """Dense-vector retrieval over approved, chunked corpus documents."""

    def __init__(
        self,
        corpus_path: Path,
        *,
        top_k: int,
        embedding_model: str,
        collection_name: str,
        local_path: Path,
        url: str | None = None,
        api_key: str | None = None,
        embedder: Embedder | None = None,
        client: Any | None = None,
    ) -> None:
        self.lexical = InvestigationRetriever(corpus_path, enabled=True, top_k=top_k)
        self.top_k = top_k
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.embedder = embedder or FastEmbedEmbedder(embedding_model)
        self.client = client or self._create_client(url, api_key, local_path)
        self._sync_chunks()

    def catalog(self) -> dict[str, Any]:
        catalog = self.lexical.catalog()
        catalog["backend"] = "qdrant"
        catalog["collection"] = self.collection_name
        catalog["embedding_model"] = self.embedding_model
        return catalog

    def retrieve(self, triage: dict[str, Any]) -> dict[str, Any]:
        from qdrant_client import models

        family = str(triage["primary_family"])
        query_terms = self.lexical._query_for(triage)
        query_vector = self.embedder.embed([" ".join(sorted(query_terms))])[0]
        query_filter = models.Filter(
            must=[
                models.FieldCondition(key="approved", match=models.MatchValue(value=True)),
                models.FieldCondition(key="families", match=models.MatchValue(value=family)),
                models.FieldCondition(
                    key="corpus_version", match=models.MatchValue(value=self.lexical.version)
                ),
            ]
        )
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=self.top_k,
            with_payload=True,
        )
        chunk_by_id = {chunk.id: chunk for chunk in self.lexical.chunks}
        results: list[tuple[float, KnowledgeChunk]] = []
        for point in response.points:
            chunk_id = str((point.payload or {}).get("chunk_id", ""))
            chunk = chunk_by_id.get(chunk_id)
            if chunk is not None:
                results.append((float(point.score), chunk))
        return self.lexical._guidance_from_ranked(
            results,
            query=query_terms,
            retrieval_method="qdrant_dense_chunked_documents_with_metadata_filter",
        )

    def close(self) -> None:
        self.client.close()

    def _create_client(self, url: str | None, api_key: str | None, local_path: Path) -> Any:
        from qdrant_client import QdrantClient

        if url and url.strip():
            return QdrantClient(url=url.strip(), api_key=api_key, timeout=15)
        local_path.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(local_path))

    def _sync_chunks(self) -> None:
        from qdrant_client import models

        texts = [chunk.searchable_text() for chunk in self.lexical.chunks]
        vectors = self.embedder.embed(texts)
        if not vectors:
            raise ValueError("The embedding provider returned no vectors for the approved document corpus")
        vector_size = len(vectors[0])
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )
        else:
            config = self.client.get_collection(self.collection_name).config.params.vectors
            existing_size = getattr(config, "size", None)
            if existing_size is not None and existing_size != vector_size:
                raise ValueError(
                    f"Qdrant collection '{self.collection_name}' uses {existing_size} dimensions, "
                    f"but the configured embedding model produces {vector_size}. Set a new "
                    "QDRANT_COLLECTION before changing embedding models."
                )
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.lexical.corpus_id}:{chunk.id}")),
                vector=vector,
                payload={
                    "chunk_id": chunk.id,
                    "document_id": chunk.document.id,
                    "approved": True,
                    "families": chunk.document.families,
                    "corpus_version": self.lexical.version,
                    "checksum": chunk.checksum,
                },
            )
            for chunk, vector in zip(self.lexical.chunks, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)


def create_investigation_retriever(settings: Settings) -> GuidanceRetriever:
    """Select an explicit backend; the default remains the portable lexical baseline."""

    backend = settings.rag_backend.strip().lower()
    if backend == "tfidf":
        return InvestigationRetriever(settings.rag_corpus_file, settings.rag_enabled, settings.rag_top_k)
    if backend == "qdrant":
        if not settings.rag_enabled:
            return InvestigationRetriever(settings.rag_corpus_file, enabled=False, top_k=settings.rag_top_k)
        return QdrantInvestigationRetriever(
            settings.rag_corpus_file,
            top_k=settings.rag_top_k,
            embedding_model=settings.rag_embedding_model,
            collection_name=settings.qdrant_collection,
            local_path=settings.qdrant_local_directory,
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    raise ValueError("RAG_BACKEND must be either 'tfidf' or 'qdrant'")
