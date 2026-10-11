import enum
import uuid

from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    VERY_SHORT = "very_short"
    SHORT = "short"
    LONG = "long"
    THEORETICAL = "theoretical"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    exam_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
    )
    question_no: Mapped[str] = mapped_column(String(10), nullable=False)
    question_text: Mapped[str] = mapped_column(String, nullable=False)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String(10), nullable=True)
    question_type: Mapped[QuestionType | None] = mapped_column(
        SQLEnum(
            QuestionType,
            name="question_type_enum",
            values_callable=lambda e: [item.value for item in e],
        ),
        nullable=True,
    )
