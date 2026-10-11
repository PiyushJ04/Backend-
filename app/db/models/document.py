import enum, uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentType(str, enum.Enum):
    QUESTION_PAPER = "question_paper"
    SYLLABUS = "syllabus"
    THEORY_NOTES = "theory_notes"
    SAMPLE_ANSWER = "sample_answer"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    exam_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("exams.id", ondelete="CASCADE")
    )

    type: Mapped[DocumentType] = mapped_column(
        SQLEnum(
            DocumentType,
            name="document_type",
            values_callable=lambda e: [i.value for i in e]
        )
    )

    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))

    # NEW (stores extracted PDF text)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # NEW relationship
    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )