from enum import Enum
from pydantic import BaseModel


class Strictness(str, Enum):
    LENIENT = "lenient"
    BALANCED = "balanced"
    STRICT = "strict"
    EXAMINER = "examiner"


class ExamCreate(BaseModel):
    subject: str
    course_code: str
    semester: int
    division: str
    strictness: Strictness = Strictness.BALANCED


class ExamResponse(BaseModel):
    id: str
    subject: str
    course_code: str
    semester: int
    division: str
    strictness: Strictness
    status: str

    class Config:
        from_attributes = True