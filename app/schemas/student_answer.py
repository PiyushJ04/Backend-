from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class StudentAnswerResponse(BaseModel):
    id: str
    question_id: str
    answer_text: str
    page_start: int | None
    page_end: int | None
    ocr_confidence: float | None
    model_config = ConfigDict(from_attributes=True)


class StudentAnswerSheetResponse(BaseModel):
    id: str
    exam_id: str
    student_identifier: str
    original_file_name: str
    page_count: int
    status: str
    error_message: str | None
    created_at: datetime
    answers: list[StudentAnswerResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class StudentAnswerSheetListResponse(BaseModel):
    success: bool
    message: str
    data: list[StudentAnswerSheetResponse]


class StudentAnswerUploadResponse(BaseModel):
    success: bool = True
    message: str
    data: list[StudentAnswerSheetResponse] = Field(default_factory=list)
    job_id: str
    job_status: str
