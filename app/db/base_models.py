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

__all__ = [
    "Base",
    "User",
    "Exam",
    "Document",
    "Question",
    "Chunk",
]