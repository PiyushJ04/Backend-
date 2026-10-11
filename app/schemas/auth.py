from pydantic import BaseModel, EmailStr


class Assignment(BaseModel):
    academic_year: str
    subject: str


class Signup(BaseModel):
    name: str
    email: EmailStr
    password: str
    department: str
    teaching_assignments: list[Assignment]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
