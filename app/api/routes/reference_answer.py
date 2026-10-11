from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.db.models.exam import Exam
from app.db.models.question import Question
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.reference_answer import (
    ReferenceAnswerRequest,
    ReferenceAnswerResponse,
    ReferenceEvidence,
)
from app.services.ai.embedding import EmbeddingConfigurationError, EmbeddingGenerationError
from app.services.ai.llm import LLMConfigurationError, LLMGenerationError
from app.services.ai.rag import KnowledgeRetrievalService
from app.services.ai.reference_answer import ReferenceAnswerAgent, ReferenceAnswerGenerationError

router = APIRouter(prefix="/exams", tags=["Reference Answer AI"])


@router.post(
    "/{exam_id}/questions/{question_id}/reference-answer/draft",
    response_model=ReferenceAnswerResponse,
)
def generate_reference_answer_draft(
    exam_id: str,
    question_id: str,
    payload: ReferenceAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
) -> ReferenceAnswerResponse:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == current_user.id))
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    question = db.scalar(
        select(Question).where(Question.id == question_id, Question.exam_id == exam_id)
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        evidence = KnowledgeRetrievalService().retrieve(
            db,
            exam_id=exam_id,
            query=question.question_text,
            top_k=payload.top_k,
            min_similarity=payload.min_similarity,
        )
        draft = ReferenceAnswerAgent().generate(
            question_no=question.question_no,
            question_text=question.question_text,
            max_marks=question.max_marks,
            evidence=evidence,
            supplemental_context=payload.academic_context,
        )
    except EmbeddingConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except EmbeddingGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (LLMGenerationError, ReferenceAnswerGenerationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    evidence_response = [
        ReferenceEvidence(
            document_id=item.document_id,
            file_name=item.file_name,
            document_type=item.document_type,
            chunk_id=item.chunk_id,
            chunk_index=item.chunk_index,
            page_number=item.page_number,
            similarity=item.cosine_similarity,
            excerpt=item.text,
        )
        for item in evidence
    ]

    return ReferenceAnswerResponse(
        success=True,
        message="Grounded reference answer draft generated successfully",
        data=draft,
        evidence=evidence_response,
    )
