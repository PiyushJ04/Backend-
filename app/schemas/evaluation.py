from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EvaluationPointResponse(BaseModel):
    point: str
    weight: Decimal
    score: Decimal


class FactorScoreResponse(BaseModel):
    id: str
    factor_id: str
    ratio: Decimal
    points: Decimal
    feedback: str

    model_config = ConfigDict(from_attributes=True)


class AnswerEvaluationResponse(BaseModel):
    id: str
    question_id: str
    baseline_ratio: Decimal
    baseline_points: Decimal
    factor_points: Decimal
    total_points: Decimal
    max_marks: Decimal
    academic_feedback: str

    matched_points: list[EvaluationPointResponse] = Field(
        default_factory=list
    )

    missing_points: list[EvaluationPointResponse] = Field(
        default_factory=list
    )

    factor_scores: list[FactorScoreResponse] = Field(
        default_factory=list
    )

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunResponse(BaseModel):
    id: str
    answer_sheet_id: str
    status: str
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    evaluations: list[AnswerEvaluationResponse] = Field(
        default_factory=list
    )

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunEnvelope(BaseModel):
    success: bool
    message: str
    data: EvaluationRunResponse