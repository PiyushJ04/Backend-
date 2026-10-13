from __future__ import annotations
import enum, uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Numeric, String, Text, func, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class EvaluationRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AnswerEvaluation(Base):
    __tablename__ = "answer_evaluations"
    __table_args__ = (UniqueConstraint("answer_sheet_id", "question_id", name="uq_answer_evaluation_sheet_question"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_sheet_id: Mapped[str] = mapped_column(String(36), ForeignKey("student_answer_sheets.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    baseline_points: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    factor_points: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    total_points: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    academic_feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    matched_points: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_points: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    run = relationship("EvaluationRun", back_populates="evaluations")
    factor_scores = relationship("FactorScore", back_populates="evaluation", cascade="all, delete-orphan")

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_sheet_id: Mapped[str] = mapped_column(String(36), ForeignKey("student_answer_sheets.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[EvaluationRunStatus] = mapped_column(SQLEnum(EvaluationRunStatus, name="evaluation_run_status_enum", values_callable=lambda e: [x.value for x in e]), nullable=False, default=EvaluationRunStatus.RUNNING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluations = relationship("AnswerEvaluation", back_populates="run", cascade="all, delete-orphan")

class FactorScore(Base):
    __tablename__ = "factor_scores"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id: Mapped[str] = mapped_column(String(36), ForeignKey("answer_evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    factor_id: Mapped[str] = mapped_column(String(36), ForeignKey("marking_factors.id", ondelete="CASCADE"), nullable=False, index=True)
    ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    points: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evaluation = relationship("AnswerEvaluation", back_populates="factor_scores")
