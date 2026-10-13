import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarkingSchemeStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class MarkingScheme(Base):
    __tablename__ = "marking_schemes"
    __table_args__ = (UniqueConstraint("question_id", name="uq_marking_scheme_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_weight: Mapped[Numeric] = mapped_column(Numeric(5, 2), nullable=False, default=75)
    factor_weight: Mapped[Numeric] = mapped_column(Numeric(5, 2), nullable=False, default=25)
    status: Mapped[MarkingSchemeStatus] = mapped_column(
        SQLEnum(MarkingSchemeStatus, name="marking_scheme_status_enum", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
        default=MarkingSchemeStatus.DRAFT,
    )
    teacher_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarkingFactor(Base):
    __tablename__ = "marking_factors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("marking_schemes.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    weight_percent: Mapped[Numeric] = mapped_column(Numeric(5, 2), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
