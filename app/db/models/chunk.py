import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE")
    )

    chunk_index: Mapped[int] = mapped_column(Integer)

    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chunk_text: Mapped[str] = mapped_column(Text)

    embedding: Mapped[list[float]] = mapped_column(Vector(384))

    document = relationship(
        "Document",
        back_populates="chunks"
    )