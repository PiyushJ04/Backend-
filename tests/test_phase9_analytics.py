from datetime import datetime, timezone
from decimal import Decimal

from app.db.models.evaluation import EvaluationRun, EvaluationRunStatus
from app.services.analytics_service import AnalyticsService


def test_analytics_percentage_summary():
    summary = AnalyticsService.summarize_percentages([
        Decimal("50"),
        Decimal("75"),
        Decimal("100"),
    ])
    assert summary["average"] == Decimal("75.00")
    assert summary["median"] == Decimal("75.00")
    assert summary["minimum"] == Decimal("50.00")
    assert summary["maximum"] == Decimal("100.00")


def test_analytics_empty_percentage_summary():
    summary = AnalyticsService.summarize_percentages([])
    assert summary["average"] == Decimal("0")
    assert summary["median"] == Decimal("0")
    assert summary["standard_deviation"] == Decimal("0")


def test_latest_completed_run_per_student():
    older = EvaluationRun(
        answer_sheet_id="sheet-1",
        status=EvaluationRunStatus.COMPLETED,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = EvaluationRun(
        answer_sheet_id="sheet-1",
        status=EvaluationRunStatus.COMPLETED,
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    failed = EvaluationRun(
        answer_sheet_id="sheet-2",
        status=EvaluationRunStatus.FAILED,
        created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )
    latest = AnalyticsService._latest_completed_runs([older, newer, failed])
    assert latest["sheet-1"] is newer
    assert "sheet-2" not in latest
