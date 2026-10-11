"""Deterministic parser for theoretical question-paper PDFs.

Phase 4 deliberately does not use an LLM.  The parser first isolates the
actual question-paper region, detects section boundaries/marks, then extracts
numbered top-level questions only inside those sections.  This prevents
instructions, page headers, answer keys, and marking guides from becoming
questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedQuestion:
    question_no: str
    question_text: str
    max_marks: int
    section: str | None = None
    question_type: str | None = None


@dataclass(frozen=True)
class _Section:
    name: str
    start: int
    end: int
    max_marks: int
    question_type: str
_QUESTION_RE = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,3})\s*[\.)\-:]\s*(.*)$",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"^\s*SECTION\s+([A-Z])\s*:\s*(.*)$", re.IGNORECASE)
_SECTION_MARKS_RE = re.compile(r"\(\s*\d+\s*[x×]\s*(\d+)\b", re.IGNORECASE)
_MARKS_RE = re.compile(
    r"(?:\[\s*(\d{1,3})\s*(?:marks?|m)?\s*\]"
    r"|\(\s*(\d{1,3})\s*(?:marks?|m)?\s*\)"
    r"|\b(\d{1,3})\s*marks?\b"
    r"|\bmarks?\s*[:\-]?\s*(\d{1,3})\b)",
    re.IGNORECASE,
)
_END_RE = re.compile(r"^\s*\*{2,}\s*END\s+OF\s+QUESTION\s+PAPER\s*\*{2,}\s*$", re.IGNORECASE)
_PAGE_RE = re.compile(r"(?:\|\s*)?Page\s+\d+\s*$", re.IGNORECASE)


class QuestionPaperParseError(ValueError):
    """Raised when the extracted paper cannot be validated as a question paper."""


class QuestionPaperParser:
    """Parse and validate top-level theoretical questions deterministically."""

    @staticmethod
    def parse(text: str) -> list[ParsedQuestion]:
        lines = QuestionPaperParser._normalize_lines(text)
        lines = QuestionPaperParser._limit_to_question_paper(lines)
        sections = QuestionPaperParser._detect_sections(lines)

        if sections:
            parsed = QuestionPaperParser._parse_sectioned(lines, sections)
            QuestionPaperParser._validate_sectioned(parsed, sections)
            return parsed
        parsed = QuestionPaperParser._parse_unsectioned(lines)
        if not parsed:
            raise QuestionPaperParseError("No numbered questions could be extracted from the paper")
        return parsed

    @staticmethod
    def _normalize_lines(text: str) -> list[str]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        result: list[str] = []
        for raw in normalized.split("\n"):
            line = re.sub(r"[ \t]+", " ", raw).strip()
            if not line:
                continue
            if _PAGE_RE.search(line) and ("page" in line.lower()):
                continue
            result.append(line)
        return result

    @staticmethod
    def _limit_to_question_paper(lines: list[str]) -> list[str]:
        for index, line in enumerate(lines):
            if _END_RE.match(line):
                return lines[:index]
        for index, line in enumerate(lines):
            if re.search(r"\b(?:ANSWER\s+KEY|MARKING\s+GUIDE)\b", line, re.IGNORECASE):
                return lines[:index]
        return lines

    @staticmethod
    def _detect_sections(lines: list[str]) -> list[_Section]:
        headers: list[tuple[int, str, str]] = []
        for index, line in enumerate(lines):
            match = _SECTION_RE.match(line)
            if match:
                headers.append((index, match.group(1).upper(), match.group(2)))

        sections: list[_Section] = []
        for position, (start, name, title) in enumerate(headers):
            end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
            window = " ".join(lines[start:min(end, start + 8)])
            marks_match = _SECTION_MARKS_RE.search(window)
            if not marks_match:
                marks_match = re.search(r"\b\d+\s*[x×]\s*(\d+)\b", window, re.IGNORECASE)
            if not marks_match:
                raise QuestionPaperParseError(
                    f"Could not determine marks for Section {name}"
                )
            max_marks = int(marks_match.group(1))
            question_type = QuestionPaperParser._question_type(title)
            sections.append(_Section(name, start, end, max_marks, question_type))

        return sections

    @staticmethod
    def _question_type(title: str) -> str:
        title_lower = title.lower()
        if "multiple choice" in title_lower or "mcq" in title_lower:
            return "mcq"
        if "very short" in title_lower:
            return "very_short"
        if "short" in title_lower:
            return "short"
        if "long" in title_lower:
            return "long"
        return "theoretical"

    @staticmethod
    def _parse_sectioned(lines: list[str], sections: list[_Section]) -> list[ParsedQuestion]:
        parsed: list[ParsedQuestion] = []
        for section in sections:
            current_no: str | None = None
            current_lines: list[str] = []

            def flush() -> None:
                nonlocal current_no, current_lines
                if current_no is None:
                    return
                question_text = QuestionPaperParser._clean_question_text(" ".join(current_lines))
                if question_text:
                    parsed.append(
                        ParsedQuestion(
                            question_no=current_no,
                            question_text=question_text,
                            max_marks=section.max_marks,
                            section=section.name,
                            question_type=section.question_type,
                        )
                    )
                current_no = None
                current_lines = []

            for line in lines[section.start + 1 : section.end]:
                match = _QUESTION_RE.match(line)
                if match:
                    flush()
                    current_no = match.group(1)
                    remainder = match.group(2).strip()
                    if remainder:
                        current_lines = [remainder]
                    continue
                if current_no is not None:
                    current_lines.append(line)

            flush()
        return parsed

    @staticmethod
    def _parse_unsectioned(lines: list[str]) -> list[ParsedQuestion]:
        questions: list[tuple[str, list[str]]] = []
        current_no: str | None = None
        current_lines: list[str] = []
        started = False

        for line in lines:
            match = _QUESTION_RE.match(line)
            if match:
                started = True
                if current_no is not None:
                    questions.append((current_no, current_lines))
                current_no = match.group(1)
                current_lines = [match.group(2).strip()] if match.group(2).strip() else []
                continue
            if started and current_no is not None:
                current_lines.append(line)

        if current_no is not None:
            questions.append((current_no, current_lines))

        parsed: list[ParsedQuestion] = []
        for question_no, question_lines in questions:
            raw_text = " ".join(question_lines).strip()
            marks = QuestionPaperParser._extract_marks(raw_text)
            clean_text = QuestionPaperParser._clean_question_text(raw_text)
            if clean_text:
                parsed.append(
                    ParsedQuestion(
                        question_no=question_no,
                        question_text=clean_text,
                        max_marks=marks,
                    )
                )
        return parsed

    @staticmethod
    def _clean_question_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        # Remove explicit per-question mark annotations such as [4], [10],
        # [5 Marks]. Section marks remain the authoritative max_marks value.
        text = re.sub(r"\[\s*\d{1,3}\s*(?:marks?|m)?\s*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\b\d{1,3}\s*marks?\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\(\s*\d{1,3}\s*(?:marks?|m)?\s*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bmarks?\s*[:\-]?\s*\d{1,3}\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip(" -")

    @staticmethod
    def _extract_marks(text: str) -> int:
        match = _MARKS_RE.search(text)
        if not match:
            return 0
        for group in match.groups():
            if group:
                return int(group)
        return 0

    @staticmethod
    def _validate_sectioned(parsed: list[ParsedQuestion], sections: list[_Section]) -> None:
        if not parsed:
            raise QuestionPaperParseError("No questions were found inside the detected sections")

        # Validate contiguous, unique numbering. This catches accidental
        # parsing of instructions or teacher answer-key content.
        numbers = [int(q.question_no) for q in parsed if q.question_no.isdigit()]
        if len(numbers) != len(parsed):
            raise QuestionPaperParseError("All extracted questions must have numeric question numbers")
        if len(numbers) != len(set(numbers)):
            raise QuestionPaperParseError("Duplicate question numbers detected")

        expected = list(range(min(numbers), max(numbers) + 1))
        if numbers != expected:
            raise QuestionPaperParseError(
                f"Question numbering is not contiguous: detected {numbers}"
            )

        # Validate section membership and marks. Counts are intentionally not
        # derived from the "attempt any" number; we validate the actual parsed
        # questions instead.
        for section in sections:
            section_questions = [q for q in parsed if q.section == section.name]
            if not section_questions:
                raise QuestionPaperParseError(f"Section {section.name} contains no questions")
            if any(q.max_marks != section.max_marks for q in section_questions):
                raise QuestionPaperParseError(
                    f"Section {section.name} has inconsistent question marks"
                )

        # Teacher-only material must never leak into question text.
        forbidden = ("MARKING GUIDE", "ANSWER KEY", "END OF QUESTION PAPER")
        for question in parsed:
            upper = question.question_text.upper()
            if any(token in upper for token in forbidden):
                raise QuestionPaperParseError(
                    f"Teacher-only content leaked into question {question.question_no}"
                )
