from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_password_already_set
from app.db.models.exam import Exam
from app.db.models.student_answer import StudentAnswerSheet
from app.db.models.evaluation import EvaluationRun, AnswerEvaluation
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.evaluation import EvaluationRunEnvelope, EvaluationRunResponse, AnswerEvaluationResponse, FactorScoreResponse
from app.services.evaluation_service import EvaluationError, EvaluationService
from app.services.ai.llm import LLMConfigurationError, LLMGenerationError

router = APIRouter(prefix="/exams", tags=["Phase 8 - Answer Evaluation"])

def _exam(db, exam_id, user_id):
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == user_id))
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam

def _sheet(db, exam_id, sheet_id):
    sheet = db.scalar(select(StudentAnswerSheet).where(
        StudentAnswerSheet.id == sheet_id, StudentAnswerSheet.exam_id == exam_id
    ))
    if not sheet:
        raise HTTPException(status_code=404, detail="Student answer sheet not found")
    return sheet

def _serialize(db, run):
    evaluations = db.scalars(select(AnswerEvaluation).where(AnswerEvaluation.run_id == run.id).order_by(AnswerEvaluation.question_id)).all()
    result=[]
    from app.db.models.evaluation import FactorScore
    for ev in evaluations:
        scores=db.scalars(select(FactorScore).where(FactorScore.evaluation_id==ev.id)).all()
        result.append(AnswerEvaluationResponse(
            id=ev.id, question_id=ev.question_id, baseline_ratio=ev.baseline_ratio,
            baseline_points=ev.baseline_points, factor_points=ev.factor_points,
            total_points=ev.total_points, max_marks=ev.max_marks,
            academic_feedback=ev.academic_feedback, matched_points=ev.matched_points or [],
            missing_points=ev.missing_points or [],
            factor_scores=[FactorScoreResponse.model_validate(s) for s in scores]
        ))
    return EvaluationRunResponse(
        id=run.id, answer_sheet_id=run.answer_sheet_id, status=run.status.value,
        error_message=run.error_message, created_at=run.created_at,
        completed_at=run.completed_at, evaluations=result
    )

@router.post("/{exam_id}/student-answers/{sheet_id}/evaluate", response_model=EvaluationRunEnvelope)
def evaluate_student_sheet(exam_id: str, sheet_id: str, db: Session = Depends(get_db),
                           current_user: User = Depends(require_password_already_set)):
    exam = _exam(db, exam_id, current_user.id)
    sheet = _sheet(db, exam_id, sheet_id)
    try:
        run = EvaluationService().evaluate_sheet(db, exam, sheet)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except EvaluationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return EvaluationRunEnvelope(success=True, message="Student answer sheet evaluated", data=_serialize(db, run))

@router.get("/{exam_id}/student-answers/{sheet_id}/evaluation", response_model=EvaluationRunEnvelope)
def get_student_evaluation(exam_id: str, sheet_id: str, db: Session = Depends(get_db),
                           current_user: User = Depends(require_password_already_set)):
    _exam(db, exam_id, current_user.id); _sheet(db, exam_id, sheet_id)
    run = db.scalar(select(EvaluationRun).where(EvaluationRun.answer_sheet_id == sheet_id).order_by(EvaluationRun.created_at.desc()))
    if not run:
        raise HTTPException(status_code=404, detail="No evaluation exists for this answer sheet")
    return EvaluationRunEnvelope(success=True, message="Evaluation retrieved", data=_serialize(db, run))

@router.post("/{exam_id}/student-answers/evaluate-all", response_model=list[EvaluationRunEnvelope])
def evaluate_all_student_sheets(exam_id: str, db: Session = Depends(get_db),
                                current_user: User = Depends(require_password_already_set)):
    exam = _exam(db, exam_id, current_user.id)
    sheets = db.scalars(select(StudentAnswerSheet).where(
        StudentAnswerSheet.exam_id == exam_id,
        StudentAnswerSheet.status == "ready"
    ).order_by(StudentAnswerSheet.student_identifier)).all()
    if not sheets:
        raise HTTPException(status_code=409, detail="No ready student answer sheets are available")
    results = []
    for sheet in sheets:
        try:
            run = EvaluationService().evaluate_sheet(db, exam, sheet)
        except LLMConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except LLMGenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except EvaluationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        results.append(EvaluationRunEnvelope(success=True, message=f"Evaluated {sheet.student_identifier}", data=_serialize(db, run)))
    return results
