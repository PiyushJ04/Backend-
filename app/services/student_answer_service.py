from __future__ import annotations

import hashlib
import io
import re
import shutil
import tempfile
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.exam import Exam
from app.db.models.question import Question
from app.db.models.student_answer import (
    AnswerSheetStatus,
    StudentAnswer,
    StudentAnswerSheet,
)
from app.services.pdf_parser import PDFParser


class StudentAnswerIngestionError(ValueError):
    pass


class StudentAnswerService:
    MAX_ZIP_BYTES = 100 * 1024 * 1024
    MAX_FILES = 200
    MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
    MAX_SINGLE_PDF_BYTES = 25 * 1024 * 1024

    @classmethod
    def stage_zip(
        cls,
        db: Session,
        exam: Exam,
        zip_bytes: bytes,
    ) -> list[StudentAnswerSheet]:

        if exam.status.value != "approved":
            raise StudentAnswerIngestionError(
                "Student answer sheets can be uploaded only after the exam "
                "marking scheme is approved"
            )

        if not zip_bytes:
            raise StudentAnswerIngestionError(
                "Answer-sheet ZIP is empty"
            )

        if len(zip_bytes) > cls.MAX_ZIP_BYTES:
            raise StudentAnswerIngestionError(
                "Answer-sheet ZIP exceeds the 100 MB limit"
            )

        with tempfile.TemporaryDirectory(
            prefix="student_answers_"
        ) as tmp:

            root = Path(tmp).resolve()

            try:
                with ZipFile(io.BytesIO(zip_bytes)) as archive:

                    members = [
                        m
                        for m in archive.infolist()
                        if not m.is_dir()
                    ]

                    if len(members) > cls.MAX_FILES:
                        raise StudentAnswerIngestionError(
                            "ZIP contains too many files"
                        )

                    pdf_members = [
                        m
                        for m in members
                        if m.filename.lower().endswith(".pdf")
                    ]

                    if not pdf_members:
                        raise StudentAnswerIngestionError(
                            "ZIP must contain at least one PDF answer sheet"
                        )

                    if len(pdf_members) != len(members):
                        raise StudentAnswerIngestionError(
                            "ZIP may contain only PDF answer sheets"
                        )

                    total_uncompressed = sum(
                        max(0, member.file_size)
                        for member in members
                    )

                    if (
                        total_uncompressed
                        > cls.MAX_UNCOMPRESSED_BYTES
                    ):
                        raise StudentAnswerIngestionError(
                            "ZIP uncompressed content exceeds the "
                            "500 MB safety limit"
                        )

                    for member in members:

                        if (
                            member.file_size
                            > cls.MAX_SINGLE_PDF_BYTES
                        ):
                            raise StudentAnswerIngestionError(
                                f"PDF {Path(member.filename).name} "
                                "exceeds the 25 MB per-file safety limit"
                            )

                        target = (
                            root / member.filename
                        ).resolve()

                        if root not in target.parents:
                            raise StudentAnswerIngestionError(
                                "ZIP contains an unsafe path"
                            )

                        target.parent.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        with (
                            archive.open(member) as src,
                            target.open("wb") as dst,
                        ):
                            shutil.copyfileobj(
                                src,
                                dst,
                            )

            except BadZipFile as exc:
                raise StudentAnswerIngestionError(
                    "Invalid ZIP file"
                ) from exc

            questions = list(
                db.scalars(
                    select(Question).where(
                        Question.exam_id == exam.id
                    )
                ).all()
            )

            if not questions:
                raise StudentAnswerIngestionError(
                    "Question paper must be uploaded before "
                    "student answers"
                )

            questions.sort(
                key=lambda q: _question_sort_key(
                    q.question_no
                )
            )

            sheets: list[StudentAnswerSheet] = []

            for pdf in sorted(
                (
                    p
                    for p in root.rglob("*")
                    if p.is_file()
                    and p.suffix.lower() == ".pdf"
                ),
                key=lambda p: p.name.lower(),
            ):

                student_identifier = (
                    cls.student_identifier_from_filename(
                        pdf.stem
                    )
                )

                pdf_bytes = pdf.read_bytes()

                digest = hashlib.sha256(
                    pdf_bytes
                ).hexdigest()

                storage_dir = (
                    Path("uploads/exams")
                    / exam.id
                    / "student_answers"
                )

                storage_dir.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                safe_identifier = re.sub(
                    r"[^A-Za-z0-9._-]+",
                    "_",
                    student_identifier,
                ).strip("._-") or "student"

                stored_pdf = (
                    storage_dir
                    / f"{safe_identifier}.pdf"
                )

                shutil.copy2(
                    pdf,
                    stored_pdf,
                )

                existing = db.scalar(
                    select(StudentAnswerSheet).where(
                        StudentAnswerSheet.exam_id
                        == exam.id,
                        StudentAnswerSheet.student_identifier
                        == student_identifier,
                    )
                )

                if existing:

                    db.execute(
                        delete(StudentAnswer).where(
                            StudentAnswer.answer_sheet_id
                            == existing.id
                        )
                    )

                    sheet = existing

                else:

                    sheet = StudentAnswerSheet(
                        exam_id=exam.id,
                        student_identifier=student_identifier,
                        original_file_name=pdf.name,
                        file_path=str(stored_pdf),
                        sha256=digest,
                    )

                    db.add(sheet)
                    db.flush()

                sheet.original_file_name = pdf.name
                sheet.file_path = str(stored_pdf)
                sheet.sha256 = digest
                sheet.page_count = 0
                sheet.extracted_text = None
                sheet.status = AnswerSheetStatus.INGESTED
                sheet.error_message = None

                sheets.append(sheet)

            db.commit()

            for sheet in sheets:
                db.refresh(sheet)

            return sheets

    @classmethod
    def ingest_zip(
        cls,
        db: Session,
        exam: Exam,
        zip_bytes: bytes,
    ) -> list[StudentAnswerSheet]:

        sheets = cls.stage_zip(
            db,
            exam,
            zip_bytes,
        )

        questions = list(
            db.scalars(
                select(Question).where(
                    Question.exam_id == exam.id
                )
            ).all()
        )

        questions.sort(
            key=lambda q: _question_sort_key(
                q.question_no
            )
        )

        for sheet in sheets:
            cls.process_sheet(
                db,
                exam,
                questions,
                sheet,
            )

        db.commit()

        for sheet in sheets:
            db.refresh(sheet)

        return sheets

    @classmethod
    def process_sheet(
        cls,
        db: Session,
        exam: Exam,
        questions: list[Question],
        sheet: StudentAnswerSheet,
    ) -> StudentAnswerSheet:

        try:

            pdf_path = Path(
                sheet.file_path
            )

            if not pdf_path.exists():
                raise StudentAnswerIngestionError(
                    f"Stored PDF is missing: "
                    f"{sheet.original_file_name}"
                )

            pdf_bytes = pdf_path.read_bytes()

            pages = PDFParser.extract_pages(
                pdf_bytes
            )

            sheet.page_count = len(pages)

            sheet.status = (
                AnswerSheetStatus.OCR_PROCESSED
            )

            sheet.extracted_text = (
                "\n\n".join(
                    f"[PAGE {page_no}]\n{text}"
                    for page_no, text in pages
                )
            )

            # --------------------------------------------------------
            # IMPORTANT:
            #
            # segment_answers() now understands:
            #
            # Ans 1 (a)
            # Ans 1 (b)
            # Ans 1 (c)
            #
            # Ans 2 (a)
            # Ans 2 (b)
            # Ans 2 (c)
            #
            # and groups each sub-part under its parent question.
            # --------------------------------------------------------

            segments = cls.segment_answers(
                pages,
                questions,
            )

            for question in questions:

                segment = segments.get(
                    question.id
                )

                db.add(
                    StudentAnswer(
                        answer_sheet_id=sheet.id,

                        question_id=question.id,

                        answer_text=(
                            segment.text
                            if segment
                            else ""
                        ),

                        page_start=(
                            segment.page_start
                            if segment
                            else None
                        ),

                        page_end=(
                            segment.page_end
                            if segment
                            else None
                        ),

                        ocr_confidence=None,
                    )
                )

            sheet.status = (
                AnswerSheetStatus.SEGMENTED
            )

            sheet.status = (
                AnswerSheetStatus.READY
            )

            sheet.error_message = None

            db.commit()
            db.refresh(sheet)

            return sheet

        except Exception as exc:

            db.rollback()

            fresh = db.get(
                StudentAnswerSheet,
                sheet.id,
            )

            if fresh:

                fresh.status = (
                    AnswerSheetStatus.FAILED
                )

                fresh.error_message = str(exc)[:4000]

                db.commit()
                db.refresh(fresh)

                return fresh

            raise StudentAnswerIngestionError(
                f"Failed to process "
                f"{sheet.original_file_name}: {exc}"
            ) from exc

    @classmethod
    def _process_pdf(
        cls,
        db: Session,
        exam: Exam,
        questions: list[Question],
        pdf: Path,
    ) -> StudentAnswerSheet:

        student_identifier = (
            cls.student_identifier_from_filename(
                pdf.stem
            )
        )

        storage_dir = (
            Path("uploads/exams")
            / exam.id
            / "student_answers"
        )

        storage_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_identifier = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            student_identifier,
        ).strip("._-") or "student"

        stored_pdf = (
            storage_dir
            / f"{safe_identifier}.pdf"
        )

        shutil.copy2(
            pdf,
            stored_pdf,
        )

        existing = db.scalar(
            select(StudentAnswerSheet).where(
                StudentAnswerSheet.exam_id
                == exam.id,
                StudentAnswerSheet.student_identifier
                == student_identifier,
            )
        )

        if existing:

            db.execute(
                delete(StudentAnswer).where(
                    StudentAnswer.answer_sheet_id
                    == existing.id
                )
            )

            sheet = existing

        else:

            sheet = StudentAnswerSheet(
                exam_id=exam.id,
                student_identifier=student_identifier,
                original_file_name=pdf.name,
                file_path=str(stored_pdf),
                sha256=hashlib.sha256(
                    pdf.read_bytes()
                ).hexdigest(),
            )

            db.add(sheet)
            db.flush()

        sheet.original_file_name = pdf.name
        sheet.file_path = str(stored_pdf)
        sheet.status = AnswerSheetStatus.INGESTED

        return cls.process_sheet(
            db,
            exam,
            questions,
            sheet,
        )

    @staticmethod
    def student_identifier_from_filename(
        stem: str,
    ) -> str:

        value = re.sub(
            r"\s+",
            " ",
            stem,
        ).strip()

        value = re.sub(
            r"(?i)(answer[_ -]?sheet|answers|paper)",
            "",
            value,
        ).strip(" _-")

        if not value:
            raise StudentAnswerIngestionError(
                "Each PDF filename must identify the student"
            )

        return value[:120]

    # =================================================================
    # QUESTION / SUBQUESTION SEGMENTATION
    # =================================================================

    @staticmethod
    def segment_answers(
        pages: list[tuple[int, str]],
        questions: list[Question],
    ) -> dict[str, "AnswerSegment"]:

        """
        Segment a student's answer paper into the top-level Question
        records stored in the database.

        The student paper may contain labels such as:

            Ans 1 (a)
            Ans 1 (b)
            Ans 1 (c)

            Ans 2 (a)
            Ans 2 (b)
            Ans 2 (c)

        The database currently has top-level questions:

            Question 1
            Question 2

        Therefore all sub-parts belonging to Question 1 are combined
        into the Question 1 StudentAnswer, and likewise for Question 2.

        Example:

            Ans 1 (b)
            <answer>

            Ans 1 (c)
            <answer>

            Ans 2 (a)
            <answer>

        becomes:

            Q1 -> Ans 1(b) + Ans 1(c)
            Q2 -> Ans 2(a)
        """

        if not pages or not questions:
            return {}

        # -------------------------------------------------------------
        # Sort pages
        # -------------------------------------------------------------

        page_blocks = sorted(
            pages,
            key=lambda item: item[0],
        )

        # -------------------------------------------------------------
        # Build lookup of database questions.
        #
        # "1" -> Question object
        # "2" -> Question object
        # -------------------------------------------------------------

        question_lookup: dict[str, Question] = {}

        for question in questions:

            number = _normalize_question_number(
                question.question_no
            )

            if number:
                question_lookup[number] = question

        if not question_lookup:
            return {}

        # -------------------------------------------------------------
        # Explicit sub-question patterns
        #
        # These are deliberately checked BEFORE generic "1"/"2"
        # patterns.
        #
        # Supported:
        #
        # Ans 1 (a)
        # Ans 1(a)
        # Ans 1. (a)
        # Answer 1 (b)
        # Q1 (c)
        # Q. 2 (a)
        # 1 (b)
        # 1(b)
        # 2(c)
        # -------------------------------------------------------------

        subpart_pattern = re.compile(
            r"""
            ^\s*
            (?:
                ans(?:wer)?
                |
                q(?:uestion)?
            )?
            \s*
            (?P<number>\d+(?:\.\d+)?)
            \s*
            (?:[\.\)\-:]|\s)?
            \s*
            [\(\[]?
            (?P<part>[a-z])
            [\)\]]?
            \s*
            (?:
                :|-|\.|\s
            )?
            """,
            re.IGNORECASE
            | re.VERBOSE,
        )

        # -------------------------------------------------------------
        # Generic question-start pattern.
        #
        # Used when the student paper says:
        #
        # 1.
        # 2)
        # Q1
        # Question 2
        #
        # rather than explicit sub-parts.
        # -------------------------------------------------------------

        question_pattern = re.compile(
            r"""
            ^\s*
            (?:
                q(?:uestion)?
                \s*
            )?
            (?P<number>\d+(?:\.\d+)?)
            \s*
            [\.\)\-:]?
            \s*
            """,
            re.IGNORECASE
            | re.VERBOSE,
        )

        # -------------------------------------------------------------
        # Store detected answer starts.
        #
        # tuple:
        #
        # (
        #     page_number,
        #     character_position,
        #     question,
        #     content_start,
        #     label_type,
        # )
        # -------------------------------------------------------------

        found: list[
            tuple[int, int, Question, int, str]
        ] = []

        for page_no, text in page_blocks:

            if not text:
                continue

            lines = text.splitlines(
                keepends=True
            )

            offset = 0

            for line in lines:

                line_without_newline = (
                    line.rstrip("\r\n")
                )

                # -----------------------------------------------------
                # First try explicit sub-question labels.
                # -----------------------------------------------------

                sub_match = (
                    subpart_pattern.match(
                        line_without_newline
                    )
                )

                if sub_match:

                    number = _normalize_question_number(
                        sub_match.group("number")
                    )

                    question = question_lookup.get(
                        number
                    )

                    if question:

                        found.append(
                            (
                                page_no,
                                offset,
                                question,
                                offset
                                + sub_match.end(),
                                "subpart",
                            )
                        )

                        offset += len(line)
                        continue

                # -----------------------------------------------------
                # Then try generic question labels.
                # -----------------------------------------------------

                q_match = (
                    question_pattern.match(
                        line_without_newline
                    )
                )

                if q_match:

                    number = _normalize_question_number(
                        q_match.group("number")
                    )

                    question = question_lookup.get(
                        number
                    )

                    if question:

                        # IMPORTANT:
                        #
                        # Do not treat "Ans 1(b)" as generic "1".
                        # The subpart pattern above should already have
                        # consumed it.
                        #
                        # This fallback is only for actual question
                        # headings.

                        stripped = (
                            line_without_newline
                            .strip()
                        )

                        lower = stripped.lower()

                        if not re.match(
                            r"^(?:ans(?:wer)?|q(?:uestion)?)?\s*"
                            r"\d+\s*[\(\[]?[a-z][\)\]]?",
                            lower,
                        ):

                            found.append(
                                (
                                    page_no,
                                    offset,
                                    question,
                                    offset
                                    + q_match.end(),
                                    "question",
                                )
                            )

                offset += len(line)

        # -------------------------------------------------------------
        # If no labels were detected, return blank segments.
        # -------------------------------------------------------------

        if not found:
            return {}

        # -------------------------------------------------------------
        # Sort detections by physical document position.
        # -------------------------------------------------------------

        found.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        # -------------------------------------------------------------
        # Remove duplicate detections at the same position.
        # -------------------------------------------------------------

        deduped: list[
            tuple[int, int, Question, int, str]
        ] = []

        seen_positions: set[
            tuple[int, int, str]
        ] = set()

        for item in found:

            page_no, start, question, content_start, kind = (
                item
            )

            key = (
                page_no,
                start,
                question.id,
            )

            if key in seen_positions:
                continue

            seen_positions.add(key)

            deduped.append(item)

        found = deduped

        # -------------------------------------------------------------
        # Build a lookup of page text.
        # -------------------------------------------------------------

        page_text_by_number = {
            page_no: text
            for page_no, text in page_blocks
        }

        page_numbers = [
            page_no
            for page_no, _ in page_blocks
        ]

        # -------------------------------------------------------------
        # Extract every detected block.
        #
        # Each block ends at the next detected answer/question label.
        # -------------------------------------------------------------

        segments: dict[
            str,
            AnswerSegment,
        ] = {}

        for index, (
            page_no,
            start,
            question,
            content_start,
            kind,
        ) in enumerate(found):

            # ---------------------------------------------------------
            # Determine endpoint.
            # ---------------------------------------------------------

            if index + 1 < len(found):

                next_page, next_start, _, _, _ = (
                    found[index + 1]
                )

                end_page = next_page
                end_pos = next_start

            else:

                end_page = page_no
                end_pos = len(
                    page_text_by_number[
                        page_no
                    ]
                )

            # ---------------------------------------------------------
            # Extract text spanning pages.
            # ---------------------------------------------------------

            text_parts: list[str] = []

            for current_page in page_numbers:

                if (
                    current_page < page_no
                    or current_page > end_page
                ):
                    continue

                current_text = (
                    page_text_by_number[
                        current_page
                    ]
                )

                if (
                    current_page == page_no
                    and current_page == end_page
                ):

                    text_parts.append(
                        current_text[
                            content_start:end_pos
                        ]
                    )

                elif current_page == page_no:

                    text_parts.append(
                        current_text[
                            content_start:
                        ]
                    )

                elif current_page == end_page:

                    text_parts.append(
                        current_text[
                            :end_pos
                        ]
                    )

                else:

                    text_parts.append(
                        current_text
                    )

            cleaned = (
                "\n".join(text_parts)
                .strip()
            )

            if not cleaned:
                continue

            # ---------------------------------------------------------
            # Combine multiple subparts belonging to the same
            # top-level question.
            # ---------------------------------------------------------

            existing = segments.get(
                question.id
            )

            if existing:

                combined_text = (
                    existing.text
                    + "\n\n"
                    + cleaned
                ).strip()

                segments[
                    question.id
                ] = AnswerSegment(
                    text=combined_text,
                    page_start=existing.page_start,
                    page_end=max(
                        existing.page_end or end_page,
                        end_page,
                    ),
                )

            else:

                segments[
                    question.id
                ] = AnswerSegment(
                    text=cleaned,
                    page_start=page_no,
                    page_end=end_page,
                )

        return segments


class AnswerSegment:

    def __init__(
        self,
        text: str,
        page_start: int | None,
        page_end: int | None,
    ):
        self.text = text
        self.page_start = page_start
        self.page_end = page_end


def _normalize_question_number(
    value: str | None,
) -> str:

    if not value:
        return ""

    value = str(value).strip()

    # "1.0" -> "1"
    if re.fullmatch(
        r"\d+\.0+",
        value,
    ):
        value = value.split(
            ".",
            1,
        )[0]

    return value


def _question_sort_key(
    value: str,
):
    match = re.match(
        r"(\d+)(.*)",
        value,
    )

    return (
        int(match.group(1)),
        match.group(2),
    ) if match else (
        10**9,
        value,
    )