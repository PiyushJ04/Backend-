from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.exam import ExamCreate, ExamResponse
from app.services.exam_service import ExamService

router = APIRouter(prefix="/exams", tags=["Exams"])


@router.post("", response_model=ExamResponse)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    return ExamService.create(
        db=db,
        teacher_id=current_user.id,
        payload=payload,
    )


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(
    exam_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    exam = ExamService.get_by_id(db, str(exam_id))

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    return exam