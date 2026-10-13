from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from math import sqrt
from statistics import median
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exam import Exam
from app.db.models.evaluation import AnswerEvaluation, EvaluationRun, EvaluationRunStatus, FactorScore
from app.db.models.marking_scheme import MarkingFactor, MarkingScheme, MarkingSchemeStatus
from app.db.models.question import Question
from app.db.models.student_answer import AnswerSheetStatus, StudentAnswer, StudentAnswerSheet


Q = Decimal("0.01")
ZERO = Decimal("0")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Q, rounding=ROUND_HALF_UP)


class AnalyticsError(ValueError):
    pass


class AnalyticsService:
    """Build deterministic, read-only analytics from completed evaluation runs."""

    @staticmethod
    def summarize_percentages(percentages: Iterable[Decimal]) -> dict[str, Decimal]:
        values = [Decimal(str(x)) for x in percentages]
        if not values:
            return {
                "average": ZERO,
                "median": ZERO,
                "minimum": ZERO,
                "maximum": ZERO,
                "standard_deviation": ZERO,
            }

        average = sum(values, ZERO) / Decimal(len(values))
        med = Decimal(str(median([float(x) for x in values])))
        variance = sum((x - average) ** 2 for x in values) / Decimal(len(values))
        return {
            "average": money(average),
            "median": money(med),
            "minimum": money(min(values)),
            "maximum": money(max(values)),
            "standard_deviation": money(Decimal(str(sqrt(float(variance))))),
        }

    @staticmethod
    def _latest_completed_runs(runs: Iterable[EvaluationRun]) -> dict[str, EvaluationRun]:
        latest: dict[str, EvaluationRun] = {}
        for run in runs:
            if run.status != EvaluationRunStatus.COMPLETED:
                continue
            previous = latest.get(run.answer_sheet_id)
            if previous is None or run.created_at > previous.created_at:
                latest[run.answer_sheet_id] = run
        return latest

    def build_report(self, db: Session, exam: Exam):
        questions = db.scalars(
            select(Question)
            .where(Question.exam_id == exam.id)
            .order_by(Question.question_no)
        ).all()
        sheets = db.scalars(
            select(StudentAnswerSheet)
            .where(StudentAnswerSheet.exam_id == exam.id)
            .order_by(StudentAnswerSheet.student_identifier)
        ).all()

        if not questions:
            raise AnalyticsError("Exam has no questions")

        runs = db.scalars(
            select(EvaluationRun)
            .join(StudentAnswerSheet, StudentAnswerSheet.id == EvaluationRun.answer_sheet_id)
            .where(StudentAnswerSheet.exam_id == exam.id)
            .order_by(EvaluationRun.created_at.desc())
        ).all()
        latest_runs = self._latest_completed_runs(runs)

        if not latest_runs:
            raise AnalyticsError("No completed evaluations are available for this exam")

        run_ids = [run.id for run in latest_runs.values()]
        evaluations = db.scalars(
            select(AnswerEvaluation)
            .where(AnswerEvaluation.run_id.in_(run_ids))
        ).all()

        question_by_id = {q.id: q for q in questions}
        eval_by_sheet: dict[str, list[AnswerEvaluation]] = defaultdict(list)
        eval_by_question: dict[str, list[AnswerEvaluation]] = defaultdict(list)
        for ev in evaluations:
            if ev.question_id in question_by_id:
                eval_by_sheet[ev.answer_sheet_id].append(ev)
                eval_by_question[ev.question_id].append(ev)

        answer_map = {}
        if latest_runs:
            answer_sheet_ids = list(latest_runs.keys())
            for answer in db.scalars(
                select(StudentAnswer).where(StudentAnswer.answer_sheet_id.in_(answer_sheet_ids))
            ).all():
                answer_map[(answer.answer_sheet_id, answer.question_id)] = answer
        sheet_by_id = {sheet.id: sheet for sheet in sheets}

        total_max = sum((Decimal(str(q.max_marks)) for q in questions), ZERO)

        students = []
        all_percentages = []
        all_academic = []
        all_factor = []

        for sheet_id, run in latest_runs.items():
            sheet = sheet_by_id.get(sheet_id)
            if sheet is None:
                continue
            evs = eval_by_sheet.get(sheet_id, [])
            points = sum((Decimal(str(e.total_points)) for e in evs), ZERO)
            academic = sum((Decimal(str(e.baseline_points)) for e in evs), ZERO)
            factors = sum((Decimal(str(e.factor_points)) for e in evs), ZERO)
            percentage = (points / total_max * Decimal("100")) if total_max else ZERO
            answered = sum(
                1 for q in questions
                if (answer_map.get((sheet_id, q.id)) is not None
                    and (answer_map[(sheet_id, q.id)].answer_text or "").strip())
            )
            missing = len(questions) - answered

            students.append({
                "student_identifier": sheet.student_identifier,
                "total_points": money(points),
                "max_points": money(total_max),
                "percentage": money(percentage),
                "question_count": len(questions),
                "answered_question_count": answered,
                "missing_question_count": missing,
            })
            all_percentages.append(percentage)
            all_academic.append(academic)
            all_factor.append(factors)

        students.sort(key=lambda s: (-s["percentage"], s["student_identifier"]))
        score_summary = self.summarize_percentages(all_percentages)

        question_results = []
        for q in questions:
            evs = eval_by_question.get(q.id, [])
            percentages = [
                (Decimal(str(e.total_points)) / Decimal(str(e.max_marks)) * Decimal("100"))
                if Decimal(str(e.max_marks)) else ZERO
                for e in evs
            ]
            stats = self.summarize_percentages(percentages)
            avg_points = sum((Decimal(str(e.total_points)) for e in evs), ZERO) / Decimal(len(evs)) if evs else ZERO
            avg_academic = sum((Decimal(str(e.baseline_points)) for e in evs), ZERO) / Decimal(len(evs)) if evs else ZERO
            avg_factor = sum((Decimal(str(e.factor_points)) for e in evs), ZERO) / Decimal(len(evs)) if evs else ZERO
            question_results.append({
                "question_id": q.id,
                "question_no": q.question_no,
                "max_marks": money(q.max_marks),
                "evaluated_students": len(evs),
                "average_points": money(avg_points),
                "average_percentage": stats["average"],
                "median_percentage": stats["median"],
                "minimum_percentage": stats["minimum"],
                "maximum_percentage": stats["maximum"],
                "average_academic_points": money(avg_academic),
                "average_factor_points": money(avg_factor),
            })

        factor_results = []
        factor_rows = db.execute(
            select(MarkingFactor, FactorScore, AnswerEvaluation)
            .join(MarkingScheme, MarkingScheme.id == MarkingFactor.scheme_id)
            .join(Question, Question.id == MarkingScheme.question_id)
            .join(AnswerEvaluation, AnswerEvaluation.question_id == Question.id)
            .join(EvaluationRun, EvaluationRun.id == AnswerEvaluation.run_id)
            .join(FactorScore, FactorScore.evaluation_id == AnswerEvaluation.id)
            .where(
                Question.exam_id == exam.id,
                MarkingScheme.status == MarkingSchemeStatus.APPROVED,
                EvaluationRun.id.in_(run_ids),
                MarkingFactor.enabled.is_(True),
            )
        ).all()

        grouped_factors: dict[str, list[tuple[MarkingFactor, FactorScore, AnswerEvaluation]]] = defaultdict(list)
        for factor, score, evaluation in factor_rows:
            grouped_factors[factor.id].append((factor, score, evaluation))

        for factor_id, rows in grouped_factors.items():
            factor = rows[0][0]
            ratios = [Decimal(str(score.ratio)) for _, score, _ in rows]
            points = [Decimal(str(score.points)) for _, score, _ in rows]
            student_ids = {evaluation.answer_sheet_id for _, _, evaluation in rows}
            avg_ratio = sum(ratios, ZERO) / Decimal(len(ratios))
            avg_points = sum(points, ZERO) / Decimal(len(points))
            factor_results.append({
                "factor_id": factor_id,
                "factor_name": factor.name,
                "weight_percent": money(factor.weight_percent),
                "evaluated_students": len(student_ids),
                "average_ratio": money(avg_ratio),
                "average_points": money(avg_points),
                "average_percentage_of_factor": money(avg_ratio * Decimal("100")),
            })

        factor_results.sort(key=lambda x: x["factor_name"].lower())

        latest_completed_at = max(
            (run.completed_at for run in latest_runs.values() if run.completed_at is not None),
            default=None,
        )
        summary = {
            "answer_sheets_uploaded": len(sheets),
            "ready_answer_sheets": sum(1 for s in sheets if s.status == AnswerSheetStatus.READY),
            "failed_answer_sheets": sum(1 for s in sheets if s.status == AnswerSheetStatus.FAILED),
            "evaluated_students": len(students),
            "total_questions": len(questions),
            "total_max_marks": money(total_max),
            "average_total_points": money(sum((s["total_points"] for s in students), ZERO) / Decimal(len(students))) if students else ZERO,
            "average_percentage": score_summary["average"],
            "median_percentage": score_summary["median"],
            "minimum_percentage": score_summary["minimum"],
            "maximum_percentage": score_summary["maximum"],
            "standard_deviation_percentage": score_summary["standard_deviation"],
            "average_academic_points": money(sum(all_academic, ZERO) / Decimal(len(all_academic))) if all_academic else ZERO,
            "average_factor_points": money(sum(all_factor, ZERO) / Decimal(len(all_factor))) if all_factor else ZERO,
            "evaluated_at": latest_completed_at,
        }

        return {
            "exam_id": exam.id,
            "subject": exam.subject,
            "course_code": exam.course_code,
            "semester": exam.semester,
            "division": exam.division,
            "status": exam.status.value,
            "summary": summary,
            "students": students,
            "questions": question_results,
            "factors": factor_results,
        }
