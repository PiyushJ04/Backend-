from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_password_already_set
from app.db.models.exam import Exam
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.document import KnowledgeUploadResponse
from app.services.ai.embedding import EmbeddingConfigurationError, EmbeddingGenerationError
from app.services.knowledge_service import KnowledgeService
from app.services.ai.ocr import OCRError

router = APIRouter(prefix="/exams", tags=["Knowledge"])


@router.post("/{exam_id}/knowledge", response_model=KnowledgeUploadResponse)
def upload_knowledge(
    exam_id: str,
    files: list[UploadFile] = File(...),
    type: Literal["syllabus", "theory_notes", "sample_answer"] = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_already_set),
):
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.teacher_id == current_user.id))
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    service = KnowledgeService()
    total_chunks = 0
    total_vectors = 0

    try:
        for file in files:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Knowledge files must be PDFs")
            pdf_bytes = file.file.read()
            result = service.process_pdf(
                db=db,
                exam_id=exam_id,
                file_name=file.filename,
                doc_type=type,
                pdf_bytes=pdf_bytes,
            )
            total_chunks += result["chunks"]
            total_vectors += result["vectors"]
    except HTTPException:
        raise
    except OCRError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (EmbeddingConfigurationError, EmbeddingGenerationError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    return KnowledgeUploadResponse(
        success=True,
        message="Knowledge uploaded and embedded successfully",
        data={"chunks": total_chunks, "vectors": total_vectors},
    )
