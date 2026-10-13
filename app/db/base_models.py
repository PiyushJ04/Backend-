"""
Imports every SQLAlchemy model so Alembic can discover them.
This file is NEVER imported by the models themselves.
"""

from app.db.base import Base

from app.db.models.user import User
from app.db.models.exam import Exam
from app.db.models.document import Document
from app.db.models.question import Question
from app.db.models.chunk import Chunk
from app.db.models.reference_answer import ReferenceAnswer
from app.db.models.marking_scheme import MarkingScheme, MarkingFactor
from app.db.models.background_job import BackgroundJob

__all__ = [
    "Base",
    "User",
    "Exam",
    "Document",
    "Question",
    "Chunk",
    "ReferenceAnswer",
    "MarkingScheme",
    "MarkingFactor",
    "BackgroundJob",
]

from app.db.models.student_answer import StudentAnswerSheet, StudentAnswer

from app.db.models.evaluation import EvaluationRun, AnswerEvaluation, FactorScore
