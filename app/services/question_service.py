from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.document import Document, DocumentType
from app.db.models.question import Question, QuestionType
from app.services.pdf_parser import PDFParser
from app.services.question_paper_parser import QuestionPaperParseError, QuestionPaperParser


class QuestionService:
    """Business logic for deterministic question-paper ingestion."""

    @staticmethod
    def parse_and_store(
        db: Session,
        exam_id: str,
        file_name: str,
        pdf_bytes: bytes,
        file_path: str,
    ) -> list[Question]:
        text = PDFParser.extract(pdf_bytes)
        parsed = QuestionPaperParser.parse(text)
        if not parsed:
            raise QuestionPaperParseError("No questions could be extracted from the paper")

        # Delete the previous question set and its source document only after
        # parsing/validation succeeded. This prevents a bad re-upload from
        # destroying a previously valid paper.
        db.execute(delete(Question).where(Question.exam_id == exam_id))
        db.execute(delete(Document).where(
            Document.exam_id == exam_id,
            Document.type == DocumentType.QUESTION_PAPER,
        ))

        document = Document(
            exam_id=exam_id,
            type=DocumentType.QUESTION_PAPER,
            file_name=file_name,
            file_path=file_path,
            text_content=text,
        )
        db.add(document)

        questions = [
            Question(
                exam_id=exam_id,
                question_no=item.question_no,
                question_text=item.question_text,
                max_marks=item.max_marks,
                section=item.section,
                question_type=(
                    QuestionType(item.question_type)
                    if item.question_type is not None
                    else None
                ),
            )
            for item in parsed
        ]
        db.add_all(questions)
        db.commit()

        for question in questions:
            db.refresh(question)
        return questions

    @staticmethod
    def list_questions(db: Session, exam_id: str) -> list[Question]:
        questions = list(
            db.scalars(
                select(Question).where(Question.exam_id == exam_id)
            ).all()
        )
        return sorted(
            questions,
            key=lambda question: (
                int(question.question_no)
                if question.question_no.isdigit()
                else float("inf"),
                question.question_no,
            ),
        )
