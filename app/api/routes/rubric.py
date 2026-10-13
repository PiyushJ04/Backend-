from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_password_already_set
from app.db.models.exam import Exam
from app.db.models.question import Question
from app.db.models.rubric import Rubric
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.rubric import (
    RubricApproveRequest,
    RubricDraftRequest,
    RubricEnvelope,
    RubricResponse,
)
from app.services.ai.llm import LLMConfigurationError, LLMGenerationError
from app.services.ai.rubric_generator import RubricGenerationError, RubricGeneratorAgent
from app.services.rubric_service import RubricService, RubricValidationError


router = APIRouter(prefix="/exams", tags=["Rubrics & Marking Factors"])


def _load_question(db: Session, exam_id: str, question_id: str, user_id: str):
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == user_id))
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    question = db.scalar(
        select(Question)
        .where(Question.id == question_id, Question.exam_id == exam_id)
        .options(selectinload(Question.rubric).selectinload(Rubric.factors))
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return exam, question


@router.post(
    "/{exam_id}/questions/{question_id}/rubric/draft",
    response_model=RubricEnvelope,
)
def create_rubric_draft(
    exam_id: str,
    question_id: str,
    payload: RubricDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    _, question = _load_question(db, exam_id, question_id, current_user.id)

    if question.rubric is not None and not payload.regenerate:
        raise HTTPException(
            status_code=409,
            detail="A rubric already exists; set regenerate=true to replace it",
        )

    try:
        draft = RubricGeneratorAgent().generate(
            question=question,
            reference_answer=None,
            teacher_notes=payload.teacher_notes,
        )
        rubric = RubricService.save_draft(
            db,
            question=question,
            draft=draft,
            teacher_notes=payload.teacher_notes,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (LLMGenerationError, RubricGenerationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return RubricEnvelope(
        success=True,
        message="Rubric draft generated successfully. Teacher approval is required.",
        data=RubricResponse.model_validate(rubric),
    )


@router.get(
    "/{exam_id}/questions/{question_id}/rubric",
    response_model=RubricEnvelope,
)
def get_rubric(
    exam_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    _, question = _load_question(db, exam_id, question_id, current_user.id)
    if question.rubric is None:
        raise HTTPException(status_code=404, detail="Rubric not found")

    return RubricEnvelope(
        success=True,
        message="Rubric retrieved successfully",
        data=RubricResponse.model_validate(question.rubric),
    )


@router.post(
    "/{exam_id}/questions/{question_id}/rubric/approve",
    response_model=RubricEnvelope,
)
def approve_rubric(
    exam_id: str,
    question_id: str,
    payload: RubricApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    exam, question = _load_question(db, exam_id, question_id, current_user.id)

    try:
        rubric = RubricService.approve(
            db,
            exam=exam,
            question=question,
            teacher_notes=payload.teacher_notes,
        )
    except RubricValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RubricEnvelope(
        success=True,
        message="Rubric approved successfully",
        data=RubricResponse.model_validate(rubric),
    )
