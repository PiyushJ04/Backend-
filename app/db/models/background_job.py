from __future__ import annotations
import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class BackgroundJobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class BackgroundJobType(str, enum.Enum):
    INGEST_ANSWERS = "ingest_answers"
    EVALUATE_SHEET = "evaluate_sheet"
    EVALUATE_EXAM = "evaluate_exam"

class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type: Mapped[BackgroundJobType] = mapped_column(
        SQLEnum(BackgroundJobType, name="background_job_type_enum",
               values_callable=lambda e: [x.value for x in e]), nullable=False)
    status: Mapped[BackgroundJobStatus] = mapped_column(
        SQLEnum(BackgroundJobStatus, name="background_job_status_enum",
               values_callable=lambda e: [x.value for x in e]), nullable=False,
        default=BackgroundJobStatus.QUEUED, index=True)
    sheet_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("student_answer_sheets.id", ondelete="CASCADE"), nullable=True, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
