from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum as SQLEnum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RubricStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class MarkingCategory(str, enum.Enum):
    THEORY = "theory"
    NON_THEORY = "non_theory"


class Rubric(Base):
    __tablename__ = "rubrics"
    __table_args__ = (UniqueConstraint("question_id", name="uq_rubrics_question_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RubricStatus] = mapped_column(
        SQLEnum(RubricStatus, name="rubric_status_enum",
                values_callable=lambda e: [i.value for i in e]),
        default=RubricStatus.DRAFT, nullable=False
    )
    theory_weight_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("65.00")
    )
    non_theory_weight_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("35.00")
    )
    teacher_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    question = relationship("Question", back_populates="rubric")
    factors = relationship(
        "MarkingFactor", back_populates="rubric",
        cascade="all, delete-orphan", order_by="MarkingFactor.order_index"
    )


class MarkingFactor(Base):
    __tablename__ = "marking_factors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rubric_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[MarkingCategory] = mapped_column(
        SQLEnum(MarkingCategory, name="marking_category_enum",
                values_callable=lambda e: [i.value for i in e]),
        nullable=False
    )
    weight_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    order_index: Mapped[int] = mapped_column(nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    rubric = relationship("Rubric", back_populates="factors")
