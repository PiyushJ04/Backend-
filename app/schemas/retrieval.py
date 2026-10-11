from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=10)
    min_similarity: float = Field(default=0.15, ge=-1.0, le=1.0)


class KnowledgeSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    document_type: str
    chunk_index: int
    page_number: int | None = None
    similarity: float
    excerpt: str


class KnowledgeSearchResponse(BaseModel):
    success: bool
    message: str
    data: list[KnowledgeSearchResult]
