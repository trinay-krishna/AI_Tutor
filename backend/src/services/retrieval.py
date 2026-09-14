"""Technology-scoped vector retrieval."""

from dataclasses import dataclass

from langchain_core.documents import Document as LCDocument

from src.config import get_settings
from src.services.vector_store import get_vector_store

settings = get_settings()


@dataclass
class RetrievedChunk:
    document: LCDocument
    score: float  # similarity in [0, 1]; higher is more similar


def _distance_to_similarity(distance: float) -> float:
    """PGVectorStore's default distance strategy is pgvector's `cosine_distance`
    (the `<=>` operator), which is defined as `1 - cosine_similarity` -- so the
    similarity is just its complement, clamped to [0, 1] for thresholding/display.
    """
    return max(0.0, min(1.0, 1.0 - distance))


async def retrieve(
    query: str,
    technology_id: int,
    k: int | None = None,
    max_per_document: int | None = None,
) -> list[RetrievedChunk]:
    """Top-k chunks for `query`, scoped to one technology, diversified across documents."""
    store = await get_vector_store()
    k = k or settings.rag_top_k
    max_per_document = max_per_document or settings.rag_max_chunks_per_document

    hits = await store.asimilarity_search_with_score(
        query, k=k, filter={"technology_id": {"$eq": technology_id}}
    )

    results: list[RetrievedChunk] = []
    per_doc_count: dict[str, int] = {}
    for doc, distance in hits:
        doc_id = doc.metadata.get("document_id")
        if per_doc_count.get(doc_id, 0) >= max_per_document:
            continue
        per_doc_count[doc_id] = per_doc_count.get(doc_id, 0) + 1
        results.append(RetrievedChunk(document=doc, score=_distance_to_similarity(distance)))

    return results


def above_threshold(chunks: list[RetrievedChunk], min_similarity: float | None = None) -> list[RetrievedChunk]:
    threshold = min_similarity if min_similarity is not None else settings.rag_min_similarity
    return [c for c in chunks if c.score >= threshold]
