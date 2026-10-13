import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReferenceAnswerStatus(str, enum.Enum):
    DRAFT = "draft"
    REVISION_REQUESTED = "revision_requested"
    APPROVED = "approved"


class ReferenceAnswer(Base):
    __tablename__ = "reference_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    # Structured per-sub-question answers. The Phase-12 migration already
    # creates this NOT NULL JSON column; keep the ORM model in sync with it.
    sub_answers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    key_concepts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expected_points: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    limitations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReferenceAnswerStatus] = mapped_column(
        SQLEnum(ReferenceAnswerStatus, name="reference_answer_status_enum", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
        default=ReferenceAnswerStatus.DRAFT,
    )
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
