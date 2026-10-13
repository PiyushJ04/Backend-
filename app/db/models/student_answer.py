from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnswerSheetStatus(str, enum.Enum):
    INGESTED = "ingested"
    OCR_PROCESSED = "ocr_processed"
    SEGMENTED = "segmented"
    READY = "ready"
    EVALUATED = "evaluated"
    FAILED = "failed"


class StudentAnswerSheet(Base):
    __tablename__ = "student_answer_sheets"
    __table_args__ = (UniqueConstraint("exam_id", "student_identifier", name="uq_answer_sheet_exam_student"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_identifier: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AnswerSheetStatus] = mapped_column(
        SQLEnum(AnswerSheetStatus, name="answer_sheet_status_enum", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=AnswerSheetStatus.INGESTED,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    answers = relationship("StudentAnswer", back_populates="sheet", cascade="all, delete-orphan")


class StudentAnswer(Base):
    __tablename__ = "student_answers"
    __table_args__ = (UniqueConstraint("answer_sheet_id", "question_id", name="uq_student_answer_sheet_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_sheet_id: Mapped[str] = mapped_column(String(36), ForeignKey("student_answer_sheets.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sheet = relationship("StudentAnswerSheet", back_populates="answers")
