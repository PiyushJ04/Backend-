"""Durable Celery tasks for answer-sheet evaluation.

Task payloads contain database identifiers only. The worker reloads all trusted
state from PostgreSQL and persists progress independently of Celery's result
backend so clients can poll safely after worker restarts.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models.background_job import BackgroundJob, BackgroundJobStatus, BackgroundJobType
from app.db.models.exam import Exam
from app.db.models.question import Question
from app.db.models.student_answer import StudentAnswerSheet
from app.services.evaluation_service import EvaluationError, EvaluationService
from app.services.student_answer_service import StudentAnswerService, StudentAnswerIngestionError

logger = logging.getLogger("app.workers.evaluation")

def _now():
    return datetime.now(timezone.utc)

def _load_job(db, job_id):
    job = db.get(BackgroundJob, job_id)
    if not job:
        raise LookupError(f"Background job {job_id} was not found")
    return job

@celery_app.task(bind=True, name="app.workers.evaluation_tasks.run_evaluation_job",
                 max_retries=2, default_retry_delay=30)
def run_evaluation_job(self, job_id: str):
    db = SessionLocal()
    try:
        job = _load_job(db, job_id)
        if job.status == BackgroundJobStatus.COMPLETED:
            return {"job_id": job.id, "status": job.status.value, "progress_completed": job.progress_completed}
        job.status = BackgroundJobStatus.RUNNING
        job.started_at = job.started_at or _now()
        job.error_message = None
        job.celery_task_id = self.request.id
        db.commit()

        exam = db.scalar(select(Exam).where(Exam.id == job.exam_id, Exam.teacher_id == job.requested_by))
        if not exam:
            raise EvaluationError("Exam no longer exists or is not owned by the requesting faculty member")

        if job.job_type == BackgroundJobType.INGEST_ANSWERS:
            sheets = db.scalars(select(StudentAnswerSheet).where(
                StudentAnswerSheet.exam_id == job.exam_id,
                StudentAnswerSheet.status == "ingested"
            ).order_by(StudentAnswerSheet.student_identifier)).all()
            if not sheets:
                raise EvaluationError("No staged student answer sheets are available for this upload")
            questions = db.scalars(select(Question).where(Question.exam_id == exam.id)).all()
            questions.sort(key=lambda q: (int(q.question_no) if str(q.question_no).isdigit() else 10**9, str(q.question_no)))
            job.progress_total = len(sheets)
            db.commit()
            results, failures = [], []
            for sheet in sheets:
                try:
                    processed = StudentAnswerService.process_sheet(db, exam, questions, sheet)
                    if processed.status.value == "ready":
                        results.append({"sheet_id": processed.id, "student_identifier": processed.student_identifier, "status": "ready"})
                    else:
                        failures.append({"sheet_id": processed.id, "student_identifier": processed.student_identifier, "error": processed.error_message or "OCR/segmentation failed"})
                except Exception as exc:
                    failures.append({"sheet_id": sheet.id, "student_identifier": sheet.student_identifier, "error": str(exc)})
                job = _load_job(db, job_id)
                job.progress_completed += 1
                job.result_json = {"processed": results, "failures": failures}
                db.commit()
        else:
            if job.job_type == BackgroundJobType.EVALUATE_SHEET:
                sheets = db.scalars(select(StudentAnswerSheet).where(
                    StudentAnswerSheet.id == job.sheet_id,
                    StudentAnswerSheet.exam_id == job.exam_id,
                    StudentAnswerSheet.status == "ready"
                )).all()
            else:
                sheets = db.scalars(select(StudentAnswerSheet).where(
                    StudentAnswerSheet.exam_id == job.exam_id,
                    StudentAnswerSheet.status == "ready"
                ).order_by(StudentAnswerSheet.student_identifier)).all()

            if not sheets:
                raise EvaluationError("No ready student answer sheets are available for this job")
            job.progress_total = len(sheets)
            db.commit()
            results, failures = [], []
            service = EvaluationService()
            for sheet in sheets:
                try:
                    run = service.evaluate_sheet(db, exam, sheet)
                    results.append({"sheet_id": sheet.id, "evaluation_run_id": run.id, "status": run.status.value})
                except EvaluationError as exc:
                    failures.append({"sheet_id": sheet.id, "student_identifier": sheet.student_identifier, "error": str(exc)})
                job = _load_job(db, job_id)
                job.progress_completed += 1
                job.result_json = {"completed": results, "failures": failures}
                db.commit()

        job = _load_job(db, job_id)
        job.result_json = {"completed": results, "failures": failures}
        job.completed_at = _now()
        if failures and not results:
            job.status = BackgroundJobStatus.FAILED
            action = "processing" if job.job_type == BackgroundJobType.INGEST_ANSWERS else "evaluation"
            job.error_message = f"All {len(failures)} {action}(s) failed. See the failure details in the job result."
        elif failures:
            job.status = BackgroundJobStatus.FAILED
            action = "processing" if job.job_type == BackgroundJobType.INGEST_ANSWERS else "evaluation"
            job.error_message = f"{len(failures)} of {len(sheets)} {action}(s) failed. Successful items were retained."
        else:
            job.status = BackgroundJobStatus.COMPLETED
            job.error_message = None
        db.commit()
        return {"job_id": job.id, "status": job.status.value,
                "progress_completed": job.progress_completed, "progress_total": job.progress_total}
    except EvaluationError as exc:
        db.rollback()
        job = db.get(BackgroundJob, job_id)
        if job:
            job.status = BackgroundJobStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = _now()
            db.commit()
        return {"job_id": job_id, "status": "failed", "error": str(exc)}
    except Exception as exc:
        db.rollback()
        retries = self.request.retries
        job = db.get(BackgroundJob, job_id)
        if job:
            job.status = BackgroundJobStatus.QUEUED if retries < self.max_retries else BackgroundJobStatus.FAILED
            job.error_message = f"Temporary worker error (attempt {retries + 1}): {exc}"
            if retries >= self.max_retries:
                job.completed_at = _now()
            db.commit()
        logger.exception("Evaluation job %s failed on attempt %s", job_id, retries + 1)
        if retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (retries + 1))
        return {"job_id": job_id, "status": "failed", "error": str(exc)}
    finally:
        db.close()
