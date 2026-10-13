from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsStudent(BaseModel):
    student_identifier: str
    total_points: Decimal
    max_points: Decimal
    percentage: Decimal
    question_count: int
    answered_question_count: int
    missing_question_count: int


class AnalyticsQuestion(BaseModel):
    question_id: str
    question_no: str
    max_marks: Decimal
    evaluated_students: int
    average_points: Decimal
    average_percentage: Decimal
    median_percentage: Decimal
    minimum_percentage: Decimal
    maximum_percentage: Decimal
    average_academic_points: Decimal
    average_factor_points: Decimal


class AnalyticsFactor(BaseModel):
    factor_id: str
    factor_name: str
    weight_percent: Decimal
    evaluated_students: int
    average_ratio: Decimal
    average_points: Decimal
    average_percentage_of_factor: Decimal


class AnalyticsSummary(BaseModel):
    answer_sheets_uploaded: int
    ready_answer_sheets: int
    failed_answer_sheets: int
    evaluated_students: int
    total_questions: int
    total_max_marks: Decimal
    average_total_points: Decimal
    average_percentage: Decimal
    median_percentage: Decimal
    minimum_percentage: Decimal
    maximum_percentage: Decimal
    standard_deviation_percentage: Decimal
    average_academic_points: Decimal
    average_factor_points: Decimal
    evaluated_at: datetime | None = None


class AnalyticsReport(BaseModel):
    exam_id: str
    subject: str
    course_code: str
    semester: int
    division: str
    status: str
    summary: AnalyticsSummary
    students: list[AnalyticsStudent] = Field(default_factory=list)
    questions: list[AnalyticsQuestion] = Field(default_factory=list)
    factors: list[AnalyticsFactor] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class AnalyticsEnvelope(BaseModel):
    success: bool
    message: str
    data: AnalyticsReport
