from pydantic import BaseModel, ConfigDict


class QuestionResponse(BaseModel):
    id: str
    question_no: str
    question_text: str
    max_marks: int
    section: str | None = None
    question_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class QuestionPaperUploadResponse(BaseModel):
    success: bool
    message: str
    data: list[QuestionResponse]


class QuestionListResponse(BaseModel):
    success: bool
    message: str
    data: list[QuestionResponse]
