from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exam import Exam, ExamStatus
from app.db.models.question import Question
from app.db.models.rubric import MarkingCategory, MarkingFactor, Rubric, RubricStatus
from app.services.ai.rubric_generator import RubricDraft, RubricGeneratorAgent


class RubricValidationError(ValueError):
    pass


class RubricService:
    THEORY_WEIGHT = Decimal("65")
    NON_THEORY_WEIGHT = Decimal("35")

    @classmethod
    def validate_draft(cls, draft: RubricDraft) -> None:
        RubricGeneratorAgent.validate_weights(draft)

    @classmethod
    def save_draft(
        cls, db: Session, *, question: Question, draft: RubricDraft,
        teacher_notes: str | None = None,
    ) -> Rubric:
        cls.validate_draft(draft)

        existing = db.scalar(select(Rubric).where(Rubric.question_id == question.id))
        if existing:
            db.delete(existing)
            db.flush()

        rubric = Rubric(
            question_id=question.id,
            status=RubricStatus.DRAFT,
            theory_weight_percent=cls.THEORY_WEIGHT,
            non_theory_weight_percent=cls.NON_THEORY_WEIGHT,
            teacher_notes=teacher_notes,
        )
        db.add(rubric)
        db.flush()

        for index, factor in enumerate(draft.factors):
            max_marks = (
                Decimal(str(question.max_marks)) * factor.weight_percent / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            db.add(MarkingFactor(
                rubric_id=rubric.id,
                name=factor.name,
                description=factor.description,
                category=MarkingCategory(factor.category),
                weight_percent=factor.weight_percent,
                max_marks=max_marks,
                order_index=index,
                is_required=factor.is_required,
            ))

        db.commit()
        db.refresh(rubric)
        return rubric

    @staticmethod
    def get(db: Session, question_id: str) -> Rubric | None:
        return db.scalar(select(Rubric).where(Rubric.question_id == question_id))

    @classmethod
    def approve(
        cls, db: Session, *, exam: Exam, question: Question,
        teacher_notes: str | None = None,
    ) -> Rubric:
        rubric = cls.get(db, question.id)
        if rubric is None:
            raise RubricValidationError("Create a rubric draft before approving it")

        theory = sum(
            (f.weight_percent for f in rubric.factors if f.category == MarkingCategory.THEORY),
            Decimal("0"),
        )
        non_theory = sum(
            (f.weight_percent for f in rubric.factors if f.category == MarkingCategory.NON_THEORY),
            Decimal("0"),
        )
        if theory != cls.THEORY_WEIGHT or non_theory != cls.NON_THEORY_WEIGHT:
            raise RubricValidationError(
                "Rubric weights must remain exactly 65% theory and 35% non-theory"
            )

        rubric.status = RubricStatus.APPROVED
        if teacher_notes is not None:
            rubric.teacher_notes = teacher_notes

        total_questions = db.query(Question).filter(Question.exam_id == exam.id).count()
        approved_questions = (
            db.query(Question)
            .join(Rubric, Rubric.question_id == Question.id)
            .filter(
                Question.exam_id == exam.id,
                Rubric.status == RubricStatus.APPROVED,
            )
            .count()
        )
        if total_questions and approved_questions == total_questions:
            exam.status = ExamStatus.APPROVED

        db.commit()
        db.refresh(rubric)
        return rubric
