from __future__ import annotations

import os
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.chunk import Chunk
from app.db.models.document import Document, DocumentType
from app.services.ai.embedding import EmbeddingService
from app.services.pdf_parser import PDFParser

UPLOAD_DIR = "uploads"


class KnowledgeService:
    """Ingest faculty knowledge, create real embeddings, and persist evidence atomically."""

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

        try:
            document_type = DocumentType(doc_type)
        except ValueError as exc:
            raise ValueError(f"Unsupported knowledge document type: {doc_type}") from exc

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_id = f"{uuid.uuid4()}.pdf"
        file_path = os.path.join(UPLOAD_DIR, file_id)
        file_created = False

        try:
            with open(file_path, "wb") as file:
                file.write(pdf_bytes)
            file_created = True

            pages = PDFParser.extract_pages(pdf_bytes)
            text = "\n\n".join(page_text for _, page_text in pages)
            if not text.strip():
                raise ValueError("No text could be extracted from PDF")

            document = Document(
                exam_id=exam_id,
                type=document_type,
                file_name=file_name,
                file_path=file_path,
                text_content=text,
            )
            db.add(document)
            db.flush()

            chunk_records: list[tuple[int, int | None, str]] = []
            chunk_index = 0
            chunk_size = settings.rag_chunk_size
            overlap = settings.rag_chunk_overlap
            if overlap >= chunk_size:
                raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")

            for page_number, page_text in pages:
                words = page_text.split()
                step = chunk_size - overlap
                for start in range(0, len(words), step):
                    chunk_words = words[start:start + chunk_size]
                    if not chunk_words:
                        continue
                    chunk_records.append((chunk_index, page_number, " ".join(chunk_words)))
                    chunk_index += 1

            if not chunk_records:
                raise ValueError("No searchable text chunks could be created from PDF")

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

        except Exception:
            db.rollback()
            if file_created:
                try:
                    os.remove(file_path)
                except FileNotFoundError:
                    pass
            raise
