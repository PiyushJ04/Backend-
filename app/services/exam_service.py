from sqlalchemy.orm import Session

from app.db.models.exam import Exam
from app.schemas.exam import ExamCreate


class ExamService:

    @staticmethod
    def create(
        db: Session,
        teacher_id: str,
        payload: ExamCreate,
    ) -> Exam:

        exam = Exam(
            teacher_id=teacher_id,
            subject=payload.subject,
            course_code=payload.course_code,
            semester=payload.semester,
            division=payload.division,
            strictness=payload.strictness,
        )

        db.add(exam)
        db.commit()
        db.refresh(exam)

        return exam

    @staticmethod
    def get_by_id(db: Session, exam_id: str):
        return db.query(Exam).filter(Exam.id == exam_id).first()