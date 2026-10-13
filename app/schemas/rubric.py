from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class RubricDraftRequest(BaseModel):
    teacher_notes: str | None = Field(default=None, max_length=4000)
    regenerate: bool = False


class RubricApproveRequest(BaseModel):
    teacher_notes: str | None = Field(default=None, max_length=4000)


class MarkingFactorResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    weight_percent: Decimal
    max_marks: Decimal
    order_index: int
    is_required: bool
    model_config = ConfigDict(from_attributes=True)


class RubricResponse(BaseModel):
    id: str
    question_id: str
    status: str
    theory_weight_percent: Decimal
    non_theory_weight_percent: Decimal
    teacher_notes: str | None
    factors: list[MarkingFactorResponse]
    model_config = ConfigDict(from_attributes=True)


class RubricEnvelope(BaseModel):
    success: bool
    message: str
    data: RubricResponse
