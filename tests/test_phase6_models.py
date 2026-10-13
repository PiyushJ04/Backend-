from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas.phase6 import MarkingSchemeDraftRequest


def test_marking_factors_must_total_25_percent():
    payload = MarkingSchemeDraftRequest(factors=[
        {"name": "Diagram", "description": "Correct and complete diagram", "weight_percent": 10},
        {"name": "Presentation", "description": "Clear presentation", "weight_percent": 15},
    ])
    assert sum(x.weight_percent for x in payload.factors) == Decimal("25")


def test_marking_factors_reject_wrong_total():
    with pytest.raises(ValidationError):
        MarkingSchemeDraftRequest(factors=[
            {"name": "Diagram", "description": "Correct diagram", "weight_percent": 10},
            {"name": "Presentation", "description": "Clear presentation", "weight_percent": 10},
        ])
