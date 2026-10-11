from __future__ import annotations

import os
import uuid

from sqlalchemy.orm import Session

from app.db.models.chunk import Chunk
from app.db.models.document import Document, DocumentType
from app.services.ai.embedding import EmbeddingService
from app.services.pdf_parser import PDFParser

UPLOAD_DIR = "uploads"


class KnowledgeService:
    """Ingest faculty knowledge, create real embeddings, and persist evidence."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service

    def process_pdf(
        self,
        db: Session,
        exam_id: str,
        file_name: str,
        doc_type: str,
        pdf_bytes: bytes,
    ) -> dict[str, int]:
        if not pdf_bytes:
            raise ValueError("PDF is empty")

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_id = f"{uuid.uuid4()}.pdf"
        file_path = os.path.join(UPLOAD_DIR, file_id)
        with open(file_path, "wb") as file:
            file.write(pdf_bytes)

        pages = PDFParser.extract_pages(pdf_bytes)
        text = "\n\n".join(page_text for _, page_text in pages)
        if not text.strip():
            os.remove(file_path)
            raise ValueError("No text could be extracted from PDF")

        document = Document(
            exam_id=exam_id,
            type=DocumentType(doc_type),
            file_name=file_name,
            file_path=file_path,
            text_content=text,
        )
        db.add(document)
        db.flush()

        chunk_records: list[tuple[int, int | None, str]] = []
        chunk_index = 0
        for page_number, page_text in pages:
            words = page_text.split()
            chunk_size = 400
            overlap = 60
            step = chunk_size - overlap
            for start in range(0, len(words), step):
                chunk_words = words[start:start + chunk_size]
                if not chunk_words:
                    continue
                chunk_records.append((chunk_index, page_number, " ".join(chunk_words)))
                chunk_index += 1

        embedder = self.embedding_service or EmbeddingService()
        vectors = embedder.embed([text for _, _, text in chunk_records])
        if len(vectors) != len(chunk_records):
            raise RuntimeError("Embedding count does not match chunk count")

        for (index, page_number, chunk_text), vector in zip(chunk_records, vectors):
            db.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=index,
                    page_number=page_number,
                    chunk_text=chunk_text,
                    embedding=vector,
                )
            )

        db.commit()
        return {"chunks": len(chunk_records), "vectors": len(vectors)}
