from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.db.models.exam import Exam
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.analytics import AnalyticsEnvelope
from app.services.analytics_service import AnalyticsError, AnalyticsService


router = APIRouter(prefix="/exams", tags=["Phase 9 - Analytics"])


def _exam(db: Session, exam_id: str, user_id: str) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == user_id))
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@router.get("/{exam_id}/analytics", response_model=AnalyticsEnvelope)
def get_exam_analytics(
    exam_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    exam = _exam(db, exam_id, current_user.id)
    try:
        report = AnalyticsService().build_report(db, exam)
    except AnalyticsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AnalyticsEnvelope(
        success=True,
        message="Exam analytics generated from the latest completed evaluation for each student",
        data=report,
    )
