from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.db.models.exam import Exam
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.retrieval import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
)
from app.services.ai.embedding import EmbeddingConfigurationError, EmbeddingGenerationError
from app.services.ai.rag import KnowledgeRetrievalService

router = APIRouter(prefix="/exams", tags=["Knowledge Retrieval"])


@router.post("/{exam_id}/knowledge/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    exam_id: str,
    payload: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
) -> KnowledgeSearchResponse:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == current_user.id))
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    try:
        results = KnowledgeRetrievalService().retrieve(
            db,
            exam_id=exam_id,
            query=payload.query,
            top_k=payload.top_k,
            min_similarity=payload.min_similarity,
        )
    except EmbeddingConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except EmbeddingGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return KnowledgeSearchResponse(
        success=True,
        message="Knowledge retrieved successfully",
        data=[
            KnowledgeSearchResult(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                file_name=item.file_name,
                document_type=item.document_type,
                chunk_index=item.chunk_index,
                page_number=item.page_number,
                similarity=item.cosine_similarity,
                excerpt=item.text,
            )
            for item in results
        ],
    )
