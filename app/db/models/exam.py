import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Strictness(str, enum.Enum):
    LENIENT = "lenient"
    BALANCED = "balanced"
    STRICT = "strict"
    EXAMINER = "examiner"


class ExamStatus(str, enum.Enum):
    DRAFT = "draft"
    KNOWLEDGE_UPLOADED = "knowledge_uploaded"
    REFERENCE_READY = "reference_ready"
    APPROVED = "approved"
    EVALUATING = "evaluating"
    COMPLETED = "completed"


class Exam(Base):
    __tablename__ = "exams"

    # Store UUIDs as strings (same as User model)
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    teacher_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    course_code: Mapped[str] = mapped_column(String(30), nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    division: Mapped[str] = mapped_column(String(10), nullable=False)

    strictness: Mapped[Strictness] = mapped_column(
        SQLEnum(
            Strictness,
            name="strictness_enum",
            values_callable=lambda e: [i.value for i in e],
        ),
        default=Strictness.BALANCED,
        nullable=False,
    )

    status: Mapped[ExamStatus] = mapped_column(
        SQLEnum(
            ExamStatus,
            name="exam_status_enum",
            values_callable=lambda e: [i.value for i in e],
        ),
        default=ExamStatus.DRAFT,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    teacher = relationship("User", back_populates="exams")