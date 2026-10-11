# Phase 4 — Deterministic Theoretical Question-Paper Ingestion

## Status

Phase 4 is complete for theoretical/descriptive question papers. The parser is
strictly deterministic and does not use an LLM.

## Scope

The pipeline:

1. accepts a faculty-uploaded PDF;
2. extracts text with PyMuPDF;
3. isolates the question-paper region;
4. detects Section A/B/C boundaries and section-level marks;
5. extracts only top-level numbered questions inside sections;
6. preserves `(a)`, `(b)`, code, and multi-line question content;
7. derives `max_marks` from the section when a section is present;
8. stores section and question-type metadata;
9. validates numbering, marks, and teacher-only content before persistence;
10. replaces the previous question set only after parsing succeeds.

## Teacher-only boundary

If `*** END OF QUESTION PAPER ***` is present, parsing stops immediately at that
marker. `ANSWER KEY`, `MARKING GUIDE`, and their numbered entries are therefore
never interpreted as student questions.

## Example

For the supplied OOP theory demo paper the parser produces exactly 15 questions:

- Section A: Q1–Q5, 2 marks each, `very_short`.
- Section B: Q6–Q11, 4 marks each, `short`.
- Section C: Q12–Q15, 10 marks each, `long`.

The `(6)` and `(4)` annotations inside Section C sub-parts are content-level
mark allocations; the top-level question's `max_marks` remains 10 because the
section defines the total marks for the question.

## API

`POST /api/v1/exams/{exam_id}/question-paper`

- PDF only.
- Authenticated teacher owning the exam.
- Parses and validates before changing stored questions.
- Returns structured question records.

`GET /api/v1/exams/{exam_id}/questions`

Returns questions in numeric order, including section and question type.

## Validation guarantees

A sectioned paper fails ingestion if:

- no questions are found in a section;
- question numbers are duplicated or non-contiguous;
- extracted marks disagree with the section marks;
- answer-key/marking-guide/end-marker text leaks into a question.

Failed parsing does not replace an existing valid question set.

## Architecture

```text
Question Paper PDF
       |
       v
    PyMuPDF
       |
       v
Normalize + Page-header cleanup
       |
       v
End-of-paper boundary
       |
       v
Section detection + marks
       |
       v
Top-level question extraction
       |
       v
Question text cleanup
       |
       v
Deterministic validation
       |
       v
PostgreSQL questions
```

## Next phase

Phase 5 can consume these validated questions and teacher knowledge documents
to build the RAG + LLM reference-answer agent, with teacher approval before a
reference answer becomes authoritative for evaluation.
