from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.exam import Exam, ExamStatus
from app.db.models.question import Question
from app.db.models.reference_answer import (
    ReferenceAnswer,
    ReferenceAnswerStatus,
)
from app.db.models.marking_scheme import (
    MarkingScheme,
    MarkingSchemeStatus,
    MarkingFactor,
)
from app.db.models.student_answer import (
    StudentAnswerSheet,
    StudentAnswer,
    AnswerSheetStatus,
)
from app.db.models.evaluation import (
    EvaluationRun,
    EvaluationRunStatus,
    AnswerEvaluation,
    FactorScore,
)
from app.services.ai.evaluation import (
    AnswerEvaluationAgent,
    GeneratedEvaluation,
    GeneratedEvaluationPoint,
    GeneratedFactorScore,
)


class EvaluationError(ValueError):
    pass


Q = Decimal("0.01")


def money(v: Decimal) -> Decimal:
    return Decimal(v).quantize(Q, rounding=ROUND_HALF_UP)


class EvaluationService:
    def __init__(self, agent=None):
        # Lazy construction matters for blank-answer sheets.
        # Blank answers can be scored without requiring an LLM call.
        self.agent = agent

    def _agent(self):
        if self.agent is None:
            self.agent = AnswerEvaluationAgent()
        return self.agent

    def _approved_baseline(self, db, question_id):
        return db.scalar(
            select(ReferenceAnswer)
            .where(
                ReferenceAnswer.question_id == question_id,
                ReferenceAnswer.status == ReferenceAnswerStatus.APPROVED,
            )
            .order_by(ReferenceAnswer.version.desc())
        )

    def _approved_scheme(self, db, question_id):
        return db.scalar(
            select(MarkingScheme)
            .where(
                MarkingScheme.question_id == question_id,
                MarkingScheme.status == MarkingSchemeStatus.APPROVED,
            )
        )

    @staticmethod
    def calculate_scores(
        *,
        max_marks: int,
        baseline_ratio: Decimal,
        factor_ratios: list[tuple[Decimal, Decimal]],
    ) -> tuple[Decimal, Decimal, Decimal]:

        baseline_ratio = max(
            Decimal("0"),
            min(
                Decimal("1"),
                Decimal(str(baseline_ratio)),
            ),
        )

        # Academic correctness = 75%
        baseline_points = money(
            Decimal(str(max_marks))
            * Decimal("0.75")
            * baseline_ratio
        )

        # Additional marking factors = 25%
        factor_points = Decimal("0")

        for weight_percent, ratio in factor_ratios:
            ratio = max(
                Decimal("0"),
                min(
                    Decimal("1"),
                    Decimal(str(ratio)),
                ),
            )

            factor_points += money(
                Decimal(str(max_marks))
                * (
                    Decimal(str(weight_percent))
                    / Decimal("100")
                )
                * ratio
            )

        factor_points = money(factor_points)

        total = min(
            money(
                baseline_points + factor_points
            ),
            money(
                Decimal(str(max_marks))
            ),
        )

        return (
            baseline_points,
            factor_points,
            total,
        )

    def evaluate_sheet(
        self,
        db: Session,
        exam: Exam,
        sheet: StudentAnswerSheet,
    ) -> EvaluationRun:

        # ------------------------------------------------------------
        # Validate exam
        # ------------------------------------------------------------

        if exam.status not in {
            ExamStatus.APPROVED,
            ExamStatus.EVALUATING,
            ExamStatus.COMPLETED,
        }:
            raise EvaluationError(
                "Exam must have an approved baseline and marking "
                "scheme before evaluation"
            )

        # ------------------------------------------------------------
        # Validate student sheet
        # ------------------------------------------------------------

        if sheet.status.value != "ready":
            raise EvaluationError(
                "Student answer sheet is not ready for evaluation"
            )

        # ------------------------------------------------------------
        # Load questions
        # ------------------------------------------------------------

        questions = db.scalars(
            select(Question)
            .where(
                Question.exam_id == exam.id
            )
            .order_by(
                Question.question_no
            )
        ).all()

        if not questions:
            raise EvaluationError(
                "Exam has no questions"
            )

        # ------------------------------------------------------------
        # Create evaluation run
        # ------------------------------------------------------------

        run = EvaluationRun(
            answer_sheet_id=sheet.id,
            status=EvaluationRunStatus.RUNNING,
        )

        db.add(run)
        db.flush()

        try:

            # --------------------------------------------------------
            # Remove previous evaluations
            # --------------------------------------------------------

            db.execute(
                delete(AnswerEvaluation).where(
                    AnswerEvaluation.answer_sheet_id
                    == sheet.id
                )
            )

            # --------------------------------------------------------
            # Load student answers
            # --------------------------------------------------------

            answers = {
                answer.question_id: answer
                for answer in db.scalars(
                    select(StudentAnswer).where(
                        StudentAnswer.answer_sheet_id
                        == sheet.id
                    )
                ).all()
            }

            # --------------------------------------------------------
            # Evaluate each question
            # --------------------------------------------------------

            for question in questions:

                # ----------------------------------------------------
                # Approved reference answer
                # ----------------------------------------------------

                baseline = self._approved_baseline(
                    db,
                    question.id,
                )

                # ----------------------------------------------------
                # Approved marking scheme
                # ----------------------------------------------------

                scheme = self._approved_scheme(
                    db,
                    question.id,
                )

                if not baseline or not scheme:
                    raise EvaluationError(
                        f"Question {question.question_no} is missing "
                        "an approved baseline or marking scheme"
                    )

                # ----------------------------------------------------
                # Load enabled marking factors
                # ----------------------------------------------------

                factors = db.scalars(
                    select(MarkingFactor)
                    .where(
                        MarkingFactor.scheme_id
                        == scheme.id,
                        MarkingFactor.enabled == True,
                    )
                    .order_by(
                        MarkingFactor.name
                    )
                ).all()

                total_weight = sum(
                    (
                        Decimal(
                            str(f.weight_percent)
                        )
                        for f in factors
                    ),
                    Decimal("0"),
                )

                if total_weight != Decimal("25"):
                    raise EvaluationError(
                        f"Question {question.question_no} "
                        "marking factors must total exactly 25%"
                    )

                # ----------------------------------------------------
                # Find student answer
                # ----------------------------------------------------

                answer = answers.get(
                    question.id
                )

                student_text = (
                    answer.answer_text
                    if answer
                    else ""
                ).strip()

                # ----------------------------------------------------
                # Blank answer
                # ----------------------------------------------------

                if not student_text:

                    generated = GeneratedEvaluation(
                        baseline_ratio=Decimal("0"),

                        academic_feedback=(
                            "No answer was detected for this question."
                        ),

                        matched_points=[],

                        missing_points=[
                            GeneratedEvaluationPoint(
                                point=point,
                                weight=Decimal("0"),
                                score=Decimal("0"),
                            )
                            for point in (
                                baseline.expected_points
                                or []
                            )
                        ],

                        factor_scores=[
                            GeneratedFactorScore(
                                factor_name=f.name,
                                ratio=Decimal("0"),
                                feedback=(
                                    "No answer provided."
                                ),
                            )
                            for f in factors
                        ],
                    )

                # ----------------------------------------------------
                # Non-blank answer
                # ----------------------------------------------------

                else:

                    generated = self._agent().evaluate(
                        question_text=(
                            question.question_text
                        ),

                        max_marks=(
                            question.max_marks
                        ),

                        student_answer=(
                            student_text
                        ),

                        baseline_answer=(
                            baseline.reference_answer
                        ),

                        key_concepts=(
                            baseline.key_concepts
                            or []
                        ),

                        expected_points=(
                            baseline.expected_points
                            or []
                        ),

                        factors=[
                            {
                                "name": f.name,
                                "description": f.description,
                                "weight_percent": str(
                                    f.weight_percent
                                ),
                            }
                            for f in factors
                        ],
                    )

                # ----------------------------------------------------
                # Calculate academic score
                # ----------------------------------------------------

                baseline_points, _, _ = (
                    self.calculate_scores(
                        max_marks=question.max_marks,
                        baseline_ratio=(
                            generated.baseline_ratio
                        ),
                        factor_ratios=[],
                    )
                )

                factor_points = Decimal("0")

                # ----------------------------------------------------
                # Convert evaluation points to JSON-safe dictionaries
                # ----------------------------------------------------
                #
                # PostgreSQL JSON columns cannot serialize Pydantic
                # GeneratedEvaluationPoint objects directly.
                #
                # Therefore:
                #
                # GeneratedEvaluationPoint
                #        ↓
                # model_dump(mode="json")
                #        ↓
                # dict
                #
                # This also converts Decimal values into JSON-safe
                # representations.

                matched_points_json = [
                    point.model_dump(
                        mode="json"
                    )
                    for point in generated.matched_points
                ]

                missing_points_json = [
                    point.model_dump(
                        mode="json"
                    )
                    for point in generated.missing_points
                ]

                # ----------------------------------------------------
                # Create answer evaluation
                # ----------------------------------------------------

                evaluation = AnswerEvaluation(
                    answer_sheet_id=sheet.id,

                    question_id=question.id,

                    run_id=run.id,

                    baseline_ratio=(
                        generated.baseline_ratio
                    ),

                    baseline_points=(
                        baseline_points
                    ),

                    factor_points=Decimal("0"),

                    total_points=Decimal("0"),

                    max_marks=Decimal(
                        str(question.max_marks)
                    ),

                    academic_feedback=(
                        generated.academic_feedback
                    ),

                    # IMPORTANT:
                    # Store plain dictionaries, not Pydantic objects.
                    matched_points=(
                        matched_points_json
                    ),

                    missing_points=(
                        missing_points_json
                    ),
                )

                db.add(evaluation)
                db.flush()

                # ----------------------------------------------------
                # Index generated factor scores by name
                # ----------------------------------------------------

                generated_by_name = {
                    factor_score.factor_name
                    .strip()
                    .lower(): factor_score
                    for factor_score
                    in generated.factor_scores
                }

                # ----------------------------------------------------
                # Calculate factor scores
                # ----------------------------------------------------

                for factor in factors:

                    generated_factor = (
                        generated_by_name.get(
                            factor.name
                            .strip()
                            .lower()
                        )
                    )

                    ratio = (
                        generated_factor.ratio
                        if generated_factor
                        else Decimal("0")
                    )

                    # Clamp ratio defensively.
                    ratio = max(
                        Decimal("0"),
                        min(
                            Decimal("1"),
                            Decimal(str(ratio)),
                        ),
                    )

                    points = money(
                        Decimal(
                            str(question.max_marks)
                        )
                        * (
                            Decimal(
                                str(
                                    factor.weight_percent
                                )
                            )
                            / Decimal("100")
                        )
                        * ratio
                    )

                    factor_points += points

                    db.add(
                        FactorScore(
                            evaluation_id=(
                                evaluation.id
                            ),

                            factor_id=(
                                factor.id
                            ),

                            ratio=ratio,

                            points=points,

                            feedback=(
                                generated_factor.feedback
                                if generated_factor
                                else (
                                    "No evidence supplied "
                                    "for this factor."
                                )
                            ),
                        )
                    )

                # ----------------------------------------------------
                # Final score
                # ----------------------------------------------------

                evaluation.factor_points = money(
                    factor_points
                )

                evaluation.total_points = min(
                    money(
                        baseline_points
                        + factor_points
                    ),
                    money(
                        Decimal(
                            str(
                                question.max_marks
                            )
                        )
                    ),
                )

            # --------------------------------------------------------
            # Evaluation completed
            # --------------------------------------------------------

            run.status = (
                EvaluationRunStatus.COMPLETED
            )

            run.completed_at = (
                datetime.now(timezone.utc)
            )

            sheet.status = (
                AnswerSheetStatus.EVALUATED
            )

            # --------------------------------------------------------
            # Determine exam status
            # --------------------------------------------------------

            all_sheets = db.scalars(
                select(StudentAnswerSheet).where(
                    StudentAnswerSheet.exam_id
                    == exam.id
                )
            ).all()

            if all_sheets and all(
                s.status.value == "evaluated"
                for s in all_sheets
            ):
                exam.status = (
                    ExamStatus.COMPLETED
                )
            else:
                exam.status = (
                    ExamStatus.EVALUATING
                )

            # --------------------------------------------------------
            # Commit
            # --------------------------------------------------------

            db.commit()
            db.refresh(run)

            return run

        except Exception as exc:

            # --------------------------------------------------------
            # Rollback failed transaction
            # --------------------------------------------------------

            db.rollback()

            # --------------------------------------------------------
            # Preserve failed run for diagnostics
            # --------------------------------------------------------

            run = db.get(
                EvaluationRun,
                run.id,
            )

            if run:

                run.status = (
                    EvaluationRunStatus.FAILED
                )

                run.error_message = str(exc)

                db.commit()

            # --------------------------------------------------------
            # Preserve explicit EvaluationError
            # --------------------------------------------------------

            if isinstance(
                exc,
                EvaluationError,
            ):
                raise

            # --------------------------------------------------------
            # Wrap unexpected errors
            # --------------------------------------------------------

            raise EvaluationError(
                f"Evaluation failed: {exc}"
            ) from exc