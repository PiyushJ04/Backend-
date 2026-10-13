from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.core.celery_app import celery_app
from app.db.models.background_job import BackgroundJob, BackgroundJobStatus, BackgroundJobType
from app.db.models.exam import Exam, ExamStatus
from app.db.models.student_answer import StudentAnswerSheet
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.background_job import BackgroundJobEnvelope, BackgroundJobResponse
from app.workers.evaluation_tasks import run_evaluation_job

router = APIRouter(prefix="/exams", tags=["Phase 10 - Background Jobs"])

def _owned_exam(db: Session, exam_id: str, user_id: str) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == user_id))
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.status not in {ExamStatus.APPROVED, ExamStatus.EVALUATING, ExamStatus.COMPLETED}:
        raise HTTPException(status_code=409, detail="Exam must be approved before evaluation can be queued")
    return exam

def _queue(db: Session, *, exam: Exam, user: User, job_type: BackgroundJobType, sheet_id: str | None):
    job = BackgroundJob(exam_id=exam.id, requested_by=user.id, job_type=job_type,
                        sheet_id=sheet_id, status=BackgroundJobStatus.QUEUED,
                        progress_total=1 if sheet_id else 0, progress_completed=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        task = run_evaluation_job.apply_async(args=[job.id])
        job.celery_task_id = task.id
        db.commit()
        db.refresh(job)
    except Exception as exc:
        job.status = BackgroundJobStatus.FAILED
        job.error_message = f"Could not submit job to the task queue: {exc}"
        db.commit()
        raise HTTPException(status_code=503, detail="Background queue unavailable; ensure Redis and the Celery worker are running") from exc
    return job

@router.post("/{exam_id}/student-answers/{sheet_id}/evaluation-jobs", response_model=BackgroundJobEnvelope, status_code=202)
def queue_sheet_evaluation(exam_id: str, sheet_id: str, db: Session = Depends(get_db),
                           current_user: User = Depends(require_password_already_set)):
    exam = _owned_exam(db, exam_id, current_user.id)
    sheet = db.scalar(select(StudentAnswerSheet).where(
        StudentAnswerSheet.id == sheet_id, StudentAnswerSheet.exam_id == exam.id))
    if not sheet:
        raise HTTPException(status_code=404, detail="Student answer sheet not found")
    if sheet.status.value != "ready":
        raise HTTPException(status_code=409, detail="Student answer sheet is not ready for evaluation")
    job = _queue(db, exam=exam, user=current_user, job_type=BackgroundJobType.EVALUATE_SHEET, sheet_id=sheet.id)
    return BackgroundJobEnvelope(message="Evaluation queued", data=BackgroundJobResponse.model_validate(job))

@router.post("/{exam_id}/student-answers/evaluation-jobs", response_model=BackgroundJobEnvelope, status_code=202)
def queue_exam_evaluation(exam_id: str, db: Session = Depends(get_db),
                          current_user: User = Depends(require_password_already_set)):
    exam = _owned_exam(db, exam_id, current_user.id)
    count = db.scalar(select(StudentAnswerSheet.id).where(
        StudentAnswerSheet.exam_id == exam.id, StudentAnswerSheet.status == "ready").limit(1))
    if not count:
        raise HTTPException(status_code=409, detail="No ready student answer sheets are available")
    job = _queue(db, exam=exam, user=current_user, job_type=BackgroundJobType.EVALUATE_EXAM, sheet_id=None)
    return BackgroundJobEnvelope(message="Exam evaluation queued", data=BackgroundJobResponse.model_validate(job))

@router.get("/evaluation-jobs/{job_id}", response_model=BackgroundJobEnvelope)
def get_evaluation_job(job_id: str, db: Session = Depends(get_db),
                       current_user: User = Depends(require_password_already_set)):
    job = db.scalar(select(BackgroundJob).where(
        BackgroundJob.id == job_id, BackgroundJob.requested_by == current_user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Background job not found")
    return BackgroundJobEnvelope(message="Background job status retrieved",
                                 data=BackgroundJobResponse.model_validate(job))
