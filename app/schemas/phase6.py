from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReferenceAnswerDraftPayload(BaseModel):
    top_k: int = Field(default=5, ge=1, le=10)
    min_similarity: float = Field(default=0.15, ge=-1.0, le=1.0)
    academic_context: list[str] = Field(default_factory=list)


class ReferenceAnswerRevisionRequest(BaseModel):
    feedback: str = Field(min_length=3, max_length=5000)
    academic_context: list[str] = Field(default_factory=list)


class ReferenceAnswerVersionResponse(BaseModel):
    id: str
    question_id: str
    version: int
    reference_answer: str
    sub_answers: list[dict] = Field(default_factory=list)
    key_concepts: list[str]
    expected_points: list[str]
    limitations: list[str]
    teacher_feedback: str | None
    status: str
    created_at: datetime
    approved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ReferenceAnswerWorkflowResponse(BaseModel):
    success: bool
    message: str
    data: ReferenceAnswerVersionResponse


class MarkingFactorInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=3, max_length=1000)
    weight_percent: Decimal = Field(gt=0, le=25)
    enabled: bool = True


class MarkingSchemeDraftRequest(BaseModel):
    factors: list[MarkingFactorInput] = Field(min_length=1, max_length=10)
    teacher_notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_weights(self):
        total = sum((f.weight_percent for f in self.factors if f.enabled), Decimal("0"))
        if total != Decimal("25"):
            raise ValueError("Enabled marking factors must total exactly 25 percent")
        return self


class MarkingFactorResponse(BaseModel):
    id: str
    name: str
    description: str
    weight_percent: Decimal
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class MarkingSchemeResponse(BaseModel):
    id: str
    question_id: str
    baseline_weight: Decimal
    factor_weight: Decimal
    status: str
    teacher_notes: str | None
    factors: list[MarkingFactorResponse]
    approved_at: datetime | None


class MarkingSchemeEnvelope(BaseModel):
    success: bool
    message: str
    data: MarkingSchemeResponse | None
