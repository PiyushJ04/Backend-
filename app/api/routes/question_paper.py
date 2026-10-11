import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.db.models.exam import Exam
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.question import QuestionListResponse, QuestionPaperUploadResponse, QuestionResponse
from app.services.question_service import QuestionService

router = APIRouter(prefix="/exams", tags=["Question Paper"])


@router.post(
    "/{exam_id}/question-paper",
    response_model=QuestionPaperUploadResponse,
)
def upload_question_paper(
    exam_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
) -> QuestionPaperUploadResponse:
    """Upload a question paper, parse its questions, and persist them."""
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == current_user.id))
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Question paper must be a PDF")

    pdf_bytes = file.file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Question paper is empty")

    file_path = os.path.join("uploads", f"{uuid.uuid4()}.pdf")
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as stored_file:
        stored_file.write(pdf_bytes)

    try:
        questions = QuestionService.parse_and_store(
            db=db,
            exam_id=exam_id,
            file_name=file.filename,
            pdf_bytes=pdf_bytes,
            file_path=file_path,
        )
    except ValueError as exc:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    return QuestionPaperUploadResponse(
        success=True,
        message=f"Question paper parsed successfully: {len(questions)} questions",
        data=[QuestionResponse.model_validate(question) for question in questions],
    )


@router.get(
    "/{exam_id}/questions",
    response_model=QuestionListResponse,
)
def list_questions(
    exam_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
) -> QuestionListResponse:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == current_user.id))
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    questions = QuestionService.list_questions(db, exam_id)
    return QuestionListResponse(
        success=True,
        message="Questions retrieved successfully",
        data=[QuestionResponse.model_validate(question) for question in questions],
    )
