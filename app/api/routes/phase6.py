from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.db.models.exam import Exam, ExamStatus
from app.db.models.marking_scheme import MarkingFactor, MarkingScheme, MarkingSchemeStatus
from app.db.models.question import Question
from app.db.models.reference_answer import ReferenceAnswer, ReferenceAnswerStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.phase6 import (
    MarkingSchemeDraftRequest, MarkingSchemeEnvelope, MarkingSchemeResponse,
    MarkingFactorResponse, ReferenceAnswerDraftPayload, ReferenceAnswerRevisionRequest,
    ReferenceAnswerVersionResponse, ReferenceAnswerWorkflowResponse,
)
from app.services.ai.embedding import EmbeddingConfigurationError, EmbeddingGenerationError
from app.services.ai.llm import LLMConfigurationError, LLMGenerationError
from app.services.ai.marking_scheme import MarkingSchemeAgent, MarkingSchemeGenerationError
from app.services.ai.rag import KnowledgeRetrievalService
from app.services.ai.reference_answer import ReferenceAnswerAgent, ReferenceAnswerGenerationError

router = APIRouter(prefix="/exams", tags=["Phase 6 - Teacher Controlled Baseline"])


def _question(db: Session, exam_id: str, question_id: str, user_id: str) -> Question:
    question = db.scalar(
        select(Question).join(Exam, Exam.id == Question.exam_id).where(
            Question.id == question_id, Question.exam_id == exam_id, Exam.teacher_id == user_id
        )
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


def _approved_baseline(db: Session, question_id: str) -> ReferenceAnswer | None:
    return db.scalar(select(ReferenceAnswer).where(
        ReferenceAnswer.question_id == question_id,
        ReferenceAnswer.status == ReferenceAnswerStatus.APPROVED,
    ).order_by(ReferenceAnswer.version.desc()))


def _refresh_exam_status(db: Session, exam_id: str) -> None:
    questions = db.scalars(select(Question).where(Question.exam_id == exam_id)).all()
    if not questions:
        return
    approved_baselines = db.scalars(select(ReferenceAnswer).where(
        ReferenceAnswer.question_id.in_([q.id for q in questions]),
        ReferenceAnswer.status == ReferenceAnswerStatus.APPROVED,
    )).all()
    baseline_ids = {x.question_id for x in approved_baselines}
    approved_schemes = db.scalars(select(MarkingScheme).where(
        MarkingScheme.question_id.in_([q.id for q in questions]),
        MarkingScheme.status == MarkingSchemeStatus.APPROVED,
    )).all()
    scheme_ids = {x.question_id for x in approved_schemes}
    exam = db.get(Exam, exam_id)
    if exam:
        if all(q.id in baseline_ids and q.id in scheme_ids for q in questions):
            exam.status = ExamStatus.APPROVED
        elif baseline_ids:
            exam.status = ExamStatus.REFERENCE_READY


def _serialize_scheme(db: Session, scheme: MarkingScheme) -> MarkingSchemeResponse:
    factors = db.scalars(select(MarkingFactor).where(MarkingFactor.scheme_id == scheme.id).order_by(MarkingFactor.name)).all()
    return MarkingSchemeResponse(
        id=scheme.id, question_id=scheme.question_id,
        baseline_weight=scheme.baseline_weight, factor_weight=scheme.factor_weight,
        status=scheme.status.value, teacher_notes=scheme.teacher_notes,
        factors=[MarkingFactorResponse.model_validate(f) for f in factors],
        approved_at=scheme.approved_at,
    )


def _save_baseline(db: Session, question: Question, current_user: User, draft, feedback: str | None = None) -> ReferenceAnswer:
    latest = db.scalar(select(func.max(ReferenceAnswer.version)).where(ReferenceAnswer.question_id == question.id)) or 0
    item = ReferenceAnswer(
        question_id=question.id, version=latest + 1,
        reference_answer=draft.reference_answer,
        sub_answers=[x.model_dump() if hasattr(x, "model_dump") else x for x in draft.sub_answers],
        key_concepts=draft.key_concepts, expected_points=draft.expected_points,
        limitations=draft.limitations, teacher_feedback=feedback,
        status=ReferenceAnswerStatus.DRAFT, created_by_id=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{exam_id}/questions/{question_id}/baseline-answer/draft", response_model=ReferenceAnswerWorkflowResponse)
def create_baseline_draft(exam_id: str, question_id: str, payload: ReferenceAnswerDraftPayload,
                          db: Session = Depends(get_db), current_user: User = Depends(require_password_already_set)):
    question = _question(db, exam_id, question_id, current_user.id)
    try:
        evidence = KnowledgeRetrievalService().retrieve(db, exam_id=exam_id, query=question.question_text,
                                                        top_k=payload.top_k, min_similarity=payload.min_similarity)
        draft = ReferenceAnswerAgent().generate(question_no=question.question_no, question_text=question.question_text,
                                                max_marks=question.max_marks, evidence=evidence,
                                                supplemental_context=payload.academic_context)
    except (EmbeddingConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (EmbeddingGenerationError, LLMGenerationError, ReferenceAnswerGenerationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    item = _save_baseline(db, question, current_user, draft)
    return ReferenceAnswerWorkflowResponse(success=True, message="Baseline answer draft generated for teacher review", data=ReferenceAnswerVersionResponse.model_validate(item))


@router.post("/{exam_id}/questions/{question_id}/baseline-answer/revise", response_model=ReferenceAnswerWorkflowResponse)
def revise_baseline(exam_id: str, question_id: str, payload: ReferenceAnswerRevisionRequest,
                    db: Session = Depends(get_db), current_user: User = Depends(require_password_already_set)):
    question = _question(db, exam_id, question_id, current_user.id)
    latest = db.scalar(select(ReferenceAnswer).where(ReferenceAnswer.question_id == question.id).order_by(ReferenceAnswer.version.desc()))
    if not latest:
        raise HTTPException(status_code=409, detail="Generate a baseline draft before requesting a revision")
    try:
        evidence = KnowledgeRetrievalService().retrieve(db, exam_id=exam_id, query=question.question_text, top_k=5, min_similarity=0.15)
        context = payload.academic_context + [
            f"CURRENT BASELINE ANSWER:\n{latest.reference_answer}",
            f"TEACHER REVISION REQUEST:\n{payload.feedback}",
        ]
        draft = ReferenceAnswerAgent().generate(question_no=question.question_no, question_text=question.question_text,
                                                max_marks=question.max_marks, evidence=evidence,
                                                supplemental_context=context)
    except (EmbeddingConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (EmbeddingGenerationError, LLMGenerationError, ReferenceAnswerGenerationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    latest.status = ReferenceAnswerStatus.REVISION_REQUESTED
    item = _save_baseline(db, question, current_user, draft, feedback=payload.feedback)
    return ReferenceAnswerWorkflowResponse(success=True, message="Revised baseline generated for teacher review", data=ReferenceAnswerVersionResponse.model_validate(item))


@router.get("/{exam_id}/questions/{question_id}/baseline-answer", response_model=list[ReferenceAnswerVersionResponse])
def list_baseline_versions(exam_id: str, question_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_password_already_set)):
    question = _question(db, exam_id, question_id, current_user.id)
    versions = db.scalars(select(ReferenceAnswer).where(ReferenceAnswer.question_id == question.id).order_by(ReferenceAnswer.version.desc())).all()
    return [ReferenceAnswerVersionResponse.model_validate(v) for v in versions]


@router.post("/{exam_id}/questions/{question_id}/baseline-answer/approve", response_model=ReferenceAnswerWorkflowResponse)
def approve_baseline(exam_id: str, question_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_password_already_set)):
    question = _question(db, exam_id, question_id, current_user.id)
    latest = db.scalar(select(ReferenceAnswer).where(ReferenceAnswer.question_id == question.id).order_by(ReferenceAnswer.version.desc()))
    if not latest:
        raise HTTPException(status_code=409, detail="No baseline answer exists")
    db.query(ReferenceAnswer).filter(ReferenceAnswer.question_id == question.id, ReferenceAnswer.id != latest.id).update({ReferenceAnswer.status: ReferenceAnswerStatus.REVISION_REQUESTED}, synchronize_session=False)
    latest.status = ReferenceAnswerStatus.APPROVED
    latest.approved_at = datetime.now(timezone.utc)
    db.commit()
    _refresh_exam_status(db, exam_id)
    db.commit()
    db.refresh(latest)
    return ReferenceAnswerWorkflowResponse(success=True, message="Baseline answer approved and locked for marking", data=ReferenceAnswerVersionResponse.model_validate(latest))


@router.post("/{exam_id}/questions/{question_id}/marking-scheme/draft", response_model=MarkingSchemeEnvelope)
def draft_marking_scheme(exam_id: str, question_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_password_already_set)):
    question = _question(db, exam_id, question_id, current_user.id)
    baseline = _approved_baseline(db, question.id)
    if not baseline:
        raise HTTPException(status_code=409, detail="Approve the baseline answer before generating marking factors")
    try:
        generated = MarkingSchemeAgent().generate(question_text=question.question_text, max_marks=question.max_marks,
                                                  baseline_answer=baseline.reference_answer, key_concepts=baseline.key_concepts)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (LLMGenerationError, MarkingSchemeGenerationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    scheme = db.scalar(select(MarkingScheme).where(MarkingScheme.question_id == question.id))
    if not scheme:
        scheme = MarkingScheme(question_id=question.id, created_by_id=current_user.id)
        db.add(scheme)
        db.flush()
    else:
        scheme.status = MarkingSchemeStatus.DRAFT
        db.query(MarkingFactor).filter(MarkingFactor.scheme_id == scheme.id).delete(synchronize_session=False)
    for factor in generated.factors:
        db.add(MarkingFactor(scheme_id=scheme.id, name=factor.name, description=factor.description, weight_percent=factor.weight_percent))
    db.commit(); db.refresh(scheme)
    return MarkingSchemeEnvelope(success=True, message="Marking factors generated for teacher review", data=_serialize_scheme(db, scheme))


@router.get("/{exam_id}/questions/{question_id}/marking-scheme", response_model=MarkingSchemeEnvelope)
def get_marking_scheme(exam_id: str, question_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_password_already_set)):
    question = _question(db, exam_id, question_id, current_user.id)
    scheme = db.scalar(select(MarkingScheme).where(MarkingScheme.question_id == question.id))
    if not scheme:
        # No scheme is a normal state before factor generation. Return an empty
        # resource instead of a noisy 404 during normal workspace hydration.
        return MarkingSchemeEnvelope(success=True, message="No marking scheme has been generated yet", data=None)
    return MarkingSchemeEnvelope(success=True, message="Marking scheme retrieved", data=_serialize_scheme(db, scheme))

@router.put("/{exam_id}/questions/{question_id}/marking-scheme", response_model=MarkingSchemeEnvelope)
def update_marking_scheme(exam_id: str, question_id: str, payload: MarkingSchemeDraftRequest,
                          db: Session = Depends(get_db), current_user: User = Depends(require_password_already_set)):
    question = _question(db, exam_id, question_id, current_user.id)
    baseline = _approved_baseline(db, question.id)
    if not baseline:
        raise HTTPException(status_code=409, detail="Approve the baseline answer before editing marking factors")
    scheme = db.scalar(select(MarkingScheme).where(MarkingScheme.question_id == question.id))
    if not scheme:
        scheme = MarkingScheme(question_id=question.id, created_by_id=current_user.id)
        db.add(scheme); db.flush()
    scheme.status = MarkingSchemeStatus.DRAFT
    scheme.teacher_notes = payload.teacher_notes
    db.query(MarkingFactor).filter(MarkingFactor.scheme_id == scheme.id).delete(synchronize_session=False)
    for factor in payload.factors:
        db.add(MarkingFactor(scheme_id=scheme.id, name=factor.name, description=factor.description, weight_percent=factor.weight_percent, enabled=factor.enabled))
    db.commit(); db.refresh(scheme)
    return MarkingSchemeEnvelope(success=True, message="Marking scheme updated and ready for approval", data=_serialize_scheme(db, scheme))


@router.post("/{exam_id}/questions/{question_id}/marking-scheme/approve", response_model=MarkingSchemeEnvelope)
def approve_marking_scheme(exam_id: str, question_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_password_already_set)):
    question = _question(db, exam_id, question_id, current_user.id)
    baseline = _approved_baseline(db, question.id)
    if not baseline:
        raise HTTPException(status_code=409, detail="Approve the baseline answer before approving marking factors")
    scheme = db.scalar(select(MarkingScheme).where(MarkingScheme.question_id == question.id))
    if not scheme:
        raise HTTPException(status_code=404, detail="Marking scheme not found")
    factors = db.scalars(select(MarkingFactor).where(MarkingFactor.scheme_id == scheme.id, MarkingFactor.enabled.is_(True))).all()
    total = sum((Decimal(str(f.weight_percent)) for f in factors), Decimal("0"))
    if total != Decimal("25"):
        raise HTTPException(status_code=422, detail="Enabled marking factors must total exactly 25 percent")
    scheme.status = MarkingSchemeStatus.APPROVED
    scheme.baseline_weight = Decimal("75")
    scheme.factor_weight = Decimal("25")
    scheme.approved_at = datetime.now(timezone.utc)
    db.commit()
    _refresh_exam_status(db, exam_id)
    db.commit(); db.refresh(scheme)
    return MarkingSchemeEnvelope(success=True, message="Marking scheme approved and locked", data=_serialize_scheme(db, scheme))
