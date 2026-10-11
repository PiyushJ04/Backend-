from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.chunk import Chunk
from app.db.models.document import Document
from app.services.ai.embedding import EmbeddingService


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> list[str]:
    words = text.split()
    if not words:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    step = chunk_size - overlap
    return [
        " ".join(words[index:index + chunk_size])
        for index in range(0, len(words), step)
        if words[index:index + chunk_size]
    ]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    file_name: str
    document_type: str
    chunk_index: int
    page_number: int | None
    text: str
    cosine_similarity: float


class KnowledgeRetrievalService:
    """Retrieve exam-scoped knowledge using pgvector cosine similarity."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or EmbeddingService()

    def retrieve(
        self,
        db: Session,
        *,
        exam_id: str,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.15,
    ) -> list[RetrievedChunk]:
        query_vector = self.embedding_service.embed_query(query)

        distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
        rows = db.execute(
            select(Chunk, Document, distance)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.exam_id == exam_id)
            .order_by(distance)
            .limit(top_k)
        ).all()

        results: list[RetrievedChunk] = []
        for chunk, document, raw_distance in rows:
            similarity = 1.0 - float(raw_distance)
            if similarity < min_similarity:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    file_name=document.file_name,
                    document_type=document.type.value,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    text=chunk.chunk_text,
                    cosine_similarity=round(similarity, 6),
                )
            )
        return results
