from app.config import Settings
from app.services.retrieval import InvestigationRetriever, QdrantInvestigationRetriever


class TestEmbedder:
    """Small deterministic vectors so this test never downloads an embedding model."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        def vector(text: str) -> list[float]:
            normalized = text.lower()
            return [
                1.0 if "collision" in normalized or "ttc" in normalized else 0.01,
                1.0 if "perception" in normalized or "occlusion" in normalized else 0.01,
                1.0 if "handover" in normalized or "fallback" in normalized else 0.01,
                1.0,
            ]

        return [vector(text) for text in texts]


def test_retriever_returns_cited_safety_guidance() -> None:
    settings = Settings()
    retriever = InvestigationRetriever(settings.rag_corpus_file)

    guidance = retriever.retrieve(
        {
            "primary_family": "safety_conflict",
            "primary_family_label": "Safety conflict",
            "contributing_factors": ["Prediction and interaction"],
            "evidence": [{"metric": "minimum TTC"}],
        }
    )

    assert guidance["status"] == "available"
    assert guidance["retrieval_method"] == "local_tfidf_chunked_documents_with_family_metadata"
    assert guidance["sources"]
    assert guidance["directions"]
    assert guidance["retrieved_passages"]
    assert all(":chunk-" in passage["id"] for passage in guidance["retrieved_passages"])
    assert all(source["url"].startswith("https://") for source in guidance["sources"])

    catalog = retriever.catalog()
    assert catalog["document_count"] >= 4
    assert catalog["chunk_count"] > catalog["document_count"]


def test_retriever_can_be_disabled_without_affecting_triage_routing() -> None:
    settings = Settings()
    retriever = InvestigationRetriever(settings.rag_corpus_file, enabled=False)

    guidance = retriever.retrieve({"primary_family": "planning_control"})

    assert guidance["status"] == "disabled"
    assert guidance["sources"] == []
    assert guidance["retrieved_passages"] == []


def test_qdrant_retriever_returns_filtered_cited_guidance() -> None:
    from qdrant_client import QdrantClient

    settings = Settings()
    client = QdrantClient(location=":memory:")
    retriever = QdrantInvestigationRetriever(
        settings.rag_corpus_file,
        top_k=3,
        embedding_model="test-model",
        collection_name="test_guidance",
        local_path=settings.qdrant_local_directory,
        embedder=TestEmbedder(),
        client=client,
    )
    try:
        guidance = retriever.retrieve(
            {
                "primary_family": "safety_conflict",
                "primary_family_label": "Safety conflict",
                "contributing_factors": [],
                "evidence": [{"metric": "minimum TTC"}],
            }
        )
    finally:
        retriever.close()

    assert guidance["status"] == "available"
    assert guidance["retrieval_method"] == "qdrant_dense_chunked_documents_with_metadata_filter"
    assert guidance["sources"]
    assert guidance["retrieved_passages"]
    source_by_id = {source.id: source for source in retriever.lexical.documents}
    assert all("safety_conflict" in source_by_id[item["id"]].families for item in guidance["sources"])
    assert all("safety_conflict" in source_by_id[item["document_id"]].families for item in guidance["retrieved_passages"])
