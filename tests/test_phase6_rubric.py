from decimal import Decimal

import pytest

from app.services.ai.rubric_generator import (
    RubricDraft,
    RubricFactorDraft,
    RubricGenerationError,
)
from app.services.rubric_service import RubricService


def valid_draft():
    return RubricDraft(
        factors=[
            RubricFactorDraft(
                name="Core concepts",
                description="Correct concepts and definitions.",
                category="theory",
                weight_percent=Decimal("40"),
            ),
            RubricFactorDraft(
                name="Reasoning",
                description="Correct reasoning, derivation, or application.",
                category="theory",
                weight_percent=Decimal("25"),
            ),
            RubricFactorDraft(
                name="Coverage",
                description="Covers the required parts relevant to the question.",
                category="non_theory",
                weight_percent=Decimal("20"),
            ),
            RubricFactorDraft(
                name="Clarity",
                description="Clear and logically structured response.",
                category="non_theory",
                weight_percent=Decimal("15"),
            ),
        ]
    )


def test_phase6_weights_are_exactly_65_35():
    RubricService.validate_draft(valid_draft())


def test_phase6_rejects_wrong_theory_weight():
    draft = valid_draft()
    draft.factors[0].weight_percent = Decimal("39")
    with pytest.raises(RubricGenerationError, match="65"):
        RubricService.validate_draft(draft)


def test_phase6_rejects_wrong_non_theory_weight():
    draft = valid_draft()
    draft.factors[-1].weight_percent = Decimal("14")
    with pytest.raises(RubricGenerationError, match="35"):
        RubricService.validate_draft(draft)
