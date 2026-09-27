"""Retrieval-grounded investigation guidance for a triage case.

The corpus contains project-authored source cards rather than copied standards or PDFs.
That makes source provenance and reuse review explicit while keeping the POC portable.
"""

from __future__ import annotations

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
class KnowledgeSource:
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

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> KnowledgeSource:
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
        )

    def searchable_text(self) -> str:
        return " ".join(
            [
                self.title,
                self.publisher,
                *self.families,
                *self.keywords,
                self.summary,
                *self.investigation_prompts,
                self.limitations,
            ]
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


class GuidanceRetriever(Protocol):
    def catalog(self) -> dict[str, Any]: ...

    def retrieve(self, triage: dict[str, Any]) -> dict[str, Any]: ...

    def close(self) -> None: ...


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class InvestigationRetriever:
    """A dependency-free TF-IDF retrieval baseline with explicit family metadata.

    It is intentionally deterministic: the evidence extractor supplies the query, source
    cards are allow-listed, and all result cards are visible to the reviewer.
    """

    def __init__(self, corpus_path: Path, enabled: bool = True, top_k: int = 3) -> None:
        self.enabled = enabled
        self.top_k = top_k
        raw = json.loads(corpus_path.read_text(encoding="utf-8"))
        self.corpus_id = str(raw["corpus_id"])
        self.version = str(raw["version"])
        self.content_policy = str(raw["content_policy"])
        self.sources = [KnowledgeSource.from_dict(item) for item in raw["sources"]]
        if not self.sources:
            raise ValueError("The investigation guidance corpus is empty")
        self._document_tokens = {source.id: _tokens(source.searchable_text()) for source in self.sources}
        self._document_frequency = self._document_frequencies()

    def catalog(self) -> dict[str, Any]:
        return {
            "backend": "tfidf",
            "corpus_id": self.corpus_id,
            "version": self.version,
            "content_policy": self.content_policy,
            "sources": [source.citation(score=0.0) for source in self.sources],
        }

    def retrieve(self, triage: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {
                "status": "disabled",
                "retrieval_method": "local_tfidf_with_family_metadata",
                "decision_boundary": "No retrieved guidance is used for routing or approval.",
                "directions": [],
                "sources": [],
            }

        family = str(triage["primary_family"])
        query = self._query_for(triage)
        ranked = sorted(
            ((self._score(query, source, family), source) for source in self.sources),
            key=lambda item: item[0],
            reverse=True,
        )[: self.top_k]
        results = [(score, source) for score, source in ranked if score > 0]
        directions = [
            {"text": prompt, "source_id": source.id}
            for _, source in results
            for prompt in source.investigation_prompts[:1]
        ]
        return {
            "status": "available" if results else "no_match",
            "retrieval_method": "local_tfidf_with_family_metadata",
            "corpus_id": self.corpus_id,
            "corpus_version": self.version,
            "query_terms": sorted(query),
            "decision_boundary": (
                "Retrieved material suggests investigation directions only; it cannot establish a "
                "root cause, compliance status, routing decision, or rule approval."
            ),
            "directions": directions,
            "sources": [source.citation(score) for score, source in results],
        }

    def close(self) -> None:
        """Keep a common lifecycle interface with networked retrieval backends."""

    def _document_frequencies(self) -> dict[str, int]:
        frequencies: dict[str, int] = {}
        for tokens in self._document_tokens.values():
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

    def _score(self, query: set[str], source: KnowledgeSource, family: str) -> float:
        document = self._document_tokens[source.id]
        shared = query & document
        if not shared:
            return 0.15 if family in source.families else 0.0
        document_count = len(self.sources)

        def weight(token: str) -> float:
            return math.log((document_count + 1) / (self._document_frequency.get(token, 0) + 1)) + 1

        numerator = sum(weight(token) ** 2 for token in shared)
        query_norm = math.sqrt(sum(weight(token) ** 2 for token in query))
        document_norm = math.sqrt(sum(weight(token) ** 2 for token in document))
        cosine = numerator / (query_norm * document_norm) if query_norm and document_norm else 0.0
        return cosine + (0.18 if family in source.families else 0.0)


class FastEmbedEmbedder:
    """Local embedding provider; the selected model downloads on first Qdrant use."""

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(value) for value in vector] for vector in self.model.embed(texts)]


class QdrantInvestigationRetriever:
    """Dense-vector retrieval over the approved, project-authored source-card corpus."""

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
        self.embedder = embedder or FastEmbedEmbedder(embedding_model)
        self.client = client or self._create_client(url, api_key, local_path)
        self._sync_source_cards()

    def catalog(self) -> dict[str, Any]:
        catalog = self.lexical.catalog()
        catalog["backend"] = "qdrant"
        catalog["collection"] = self.collection_name
        catalog["embedding_model"] = type(self.embedder).__name__
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
        source_by_id = {source.id: source for source in self.lexical.sources}
        results = []
        for point in response.points:
            source_id = str((point.payload or {}).get("source_id", ""))
            source = source_by_id.get(source_id)
            if source is not None:
                results.append((float(point.score), source))

        directions = [
            {"text": prompt, "source_id": source.id}
            for _, source in results
            for prompt in source.investigation_prompts[:1]
        ]
        return {
            "status": "available" if results else "no_match",
            "retrieval_method": "qdrant_dense_cosine_with_metadata_filter",
            "corpus_id": self.lexical.corpus_id,
            "corpus_version": self.lexical.version,
            "query_terms": sorted(query_terms),
            "decision_boundary": (
                "Retrieved material suggests investigation directions only; it cannot establish a "
                "root cause, compliance status, routing decision, or rule approval."
            ),
            "directions": directions,
            "sources": [source.citation(score) for score, source in results],
        }

    def close(self) -> None:
        self.client.close()

    def _create_client(self, url: str | None, api_key: str | None, local_path: Path) -> Any:
        from qdrant_client import QdrantClient

        if url and url.strip():
            return QdrantClient(url=url.strip(), api_key=api_key, timeout=15)
        local_path.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(local_path))

    def _sync_source_cards(self) -> None:
        from qdrant_client import models

        texts = [source.searchable_text() for source in self.lexical.sources]
        vectors = self.embedder.embed(texts)
        if not vectors:
            raise ValueError("The embedding provider returned no vectors for the source-card corpus")
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
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.lexical.corpus_id}:{source.id}")),
                vector=vector,
                payload={
                    "source_id": source.id,
                    "approved": True,
                    "families": source.families,
                    "keywords": source.keywords,
                    "corpus_version": self.lexical.version,
                },
            )
            for source, vector in zip(self.lexical.sources, vectors, strict=True)
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
