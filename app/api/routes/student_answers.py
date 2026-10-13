from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.db.models.exam import Exam
from app.db.models.student_answer import StudentAnswerSheet
from app.db.models.background_job import BackgroundJob, BackgroundJobStatus, BackgroundJobType
from app.core.celery_app import celery_app
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.student_answer import StudentAnswerResponse, StudentAnswerSheetListResponse, StudentAnswerSheetResponse, StudentAnswerUploadResponse
from app.services.student_answer_service import StudentAnswerIngestionError, StudentAnswerService
from app.workers.evaluation_tasks import run_evaluation_job

router = APIRouter(prefix="/exams", tags=["Student Answer Sheets"])


def _exam(db: Session, exam_id: str, user_id: str) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == user_id))
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


def _serialize(db: Session, sheet: StudentAnswerSheet) -> StudentAnswerSheetResponse:
    return StudentAnswerSheetResponse(
        id=sheet.id,
        exam_id=sheet.exam_id,
        student_identifier=sheet.student_identifier,
        original_file_name=sheet.original_file_name,
        page_count=sheet.page_count,
        status=sheet.status.value,
        error_message=sheet.error_message,
        created_at=sheet.created_at,
        answers=[StudentAnswerResponse.model_validate(a) for a in sorted(sheet.answers, key=lambda a: a.question_id)],
    )


@router.post("/{exam_id}/student-answers", response_model=StudentAnswerUploadResponse, status_code=202)
def upload_student_answers(
    exam_id: str,
    file: UploadFile = File(..., description="ZIP containing one PDF answer sheet per student"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    exam = _exam(db, exam_id, current_user.id)
    if exam.status.value != "approved":
        raise HTTPException(status_code=409, detail="Student answer sheets can be uploaded only after the exam is approved")
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Student answer upload must be a ZIP file")

    active = db.scalar(select(BackgroundJob).where(
        BackgroundJob.exam_id == exam.id,
        BackgroundJob.requested_by == current_user.id,
        BackgroundJob.job_type == BackgroundJobType.INGEST_ANSWERS,
        BackgroundJob.status.in_([BackgroundJobStatus.QUEUED, BackgroundJobStatus.RUNNING]),
    ).order_by(BackgroundJob.created_at.desc()))
    if active:
        raise HTTPException(status_code=409, detail="An answer-sheet upload is already being processed. Wait for it to finish before uploading another ZIP.")

    try:
        sheets = StudentAnswerService.stage_zip(db, exam, file.file.read())
        job = BackgroundJob(
            exam_id=exam.id,
            requested_by=current_user.id,
            job_type=BackgroundJobType.INGEST_ANSWERS,
            status=BackgroundJobStatus.QUEUED,
            progress_total=len(sheets),
            progress_completed=0,
            result_json={"processed": [], "failures": []},
        )
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
            job.error_message = f"Could not submit upload processing job: {exc}"
            db.commit()
            raise HTTPException(status_code=503, detail="Background queue unavailable; ensure Redis and the Celery worker are running") from exc
    except StudentAnswerIngestionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return StudentAnswerUploadResponse(
        message=f"Accepted {len(sheets)} answer sheets. OCR and segmentation are running in the background.",
        data=[_serialize(db, s) for s in sheets],
        job_id=job.id,
        job_status=job.status.value,
    )


@router.get("/{exam_id}/student-answers", response_model=StudentAnswerSheetListResponse)
def list_student_answers(
    exam_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    _exam(db, exam_id, current_user.id)
    sheets = db.scalars(select(StudentAnswerSheet).where(StudentAnswerSheet.exam_id == exam_id).order_by(StudentAnswerSheet.student_identifier)).all()
    return StudentAnswerSheetListResponse(success=True, message="Student answer sheets retrieved", data=[_serialize(db, s) for s in sheets])


@router.get("/{exam_id}/student-answers/{sheet_id}", response_model=StudentAnswerSheetResponse)
def get_student_answer(
    exam_id: str,
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    _exam(db, exam_id, current_user.id)
    sheet = db.scalar(select(StudentAnswerSheet).where(StudentAnswerSheet.id == sheet_id, StudentAnswerSheet.exam_id == exam_id))
    if not sheet:
        raise HTTPException(status_code=404, detail="Student answer sheet not found")
    return _serialize(db, sheet)
