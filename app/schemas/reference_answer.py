from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceEvidence(BaseModel):
    document_id: str
    file_name: str
    document_type: str
    chunk_id: str
    chunk_index: int
    page_number: int | None = None
    similarity: float
    excerpt: str = Field(min_length=1)


class ReferenceAnswerDraft(BaseModel):
    reference_answer: str = Field(min_length=1)
    key_concepts: list[str] = Field(default_factory=list)
    expected_points: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReferenceAnswerRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=10)
    min_similarity: float = Field(default=0.15, ge=-1.0, le=1.0)
    academic_context: list[str] = Field(default_factory=list)


class ReferenceAnswerResponse(BaseModel):
    success: bool
    message: str
    data: ReferenceAnswerDraft
    evidence: list[ReferenceEvidence] = Field(default_factory=list)
