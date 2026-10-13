from decimal import Decimal
from app.services.ai.evaluation import GeneratedEvaluation, GeneratedFactorScore
from app.services.evaluation_service import EvaluationService

def test_llm_percentages_are_normalized():
    result = GeneratedEvaluation.model_validate({
        "baseline_ratio": 80,
        "academic_feedback": "Good coverage",
        "matched_points": ["encapsulation"],
        "missing_points": ["access control example"],
        "factor_scores": [{"factor_name": "Diagrams", "ratio": 50, "feedback": "Clear diagram"}],
    })
    assert result.baseline_ratio == Decimal("0.8")
    assert result.factor_scores[0].ratio == Decimal("0.5")

def test_backend_enforces_75_25_scoring():
    baseline, factors, total = EvaluationService.calculate_scores(
        max_marks=10,
        baseline_ratio=Decimal("0.8"),
        factor_ratios=[(Decimal("10"), Decimal("1")), (Decimal("15"), Decimal("0.5"))],
    )
    assert baseline == Decimal("6.00")
    assert factors == Decimal("1.75")
    assert total == Decimal("7.75")

def test_score_ratios_are_clamped():
    baseline, factors, total = EvaluationService.calculate_scores(
        max_marks=10,
        baseline_ratio=Decimal("2"),
        factor_ratios=[(Decimal("25"), Decimal("-1"))],
    )
    assert baseline == Decimal("7.50")
    assert factors == Decimal("0.00")
    assert total == Decimal("7.50")
