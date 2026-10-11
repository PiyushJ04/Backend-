# Phase 5B — Grounded RAG Knowledge Pipeline

## Status

Implemented.

Phase 5B replaces the Phase 5A zero-vector placeholder with real `BAAI/bge-small-en-v1.5` embeddings and PostgreSQL/pgvector cosine retrieval.

## Pipeline

```text
Faculty PDF
   |
   v
PyMuPDF page extraction
   |
   v
Page-aware chunks
   |
   v
BAAI/bge-small-en-v1.5 (384-D)
   |
   v
PostgreSQL + pgvector HNSW
   |
   +-----------------------------+
   |                             |
Question embedding           Retrieved evidence
   |                             |
   +-------------+---------------+
                 |
                 v
        Reference Answer Agent
                 |
                 v
        Hugging Face LLM
                 |
                 v
Teacher-reviewable answer + evidence
```

## Database changes

Migration `9d3e4f5a6b72_phase5b_rag.py`:

- enables the PostgreSQL `vector` extension;
- creates `chunks`;
- stores `page_number` for evidence traceability;
- stores `VECTOR(384)` embeddings;
- creates an HNSW cosine index.

Docker now uses `pgvector/pgvector:pg16` instead of plain PostgreSQL so the extension is available.

## Embeddings

`EmbeddingService` uses Hugging Face `InferenceClient.feature_extraction` with:

```env
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
```

Document passages are embedded directly. Queries use the BGE retrieval instruction prefix. Embeddings are L2-normalized before storage/retrieval.

## Knowledge upload

```http
POST /api/v1/exams/{exam_id}/knowledge
```

Multipart fields:

- `files`: one or more PDFs
- `type`: `syllabus`, `theory_notes`, or `sample_answer`

The endpoint now authenticates the teacher and verifies exam ownership.

## Retrieval test endpoint

```http
POST /api/v1/exams/{exam_id}/knowledge/search
```

Example:

```json
{
  "query": "Explain abstraction and encapsulation",
  "top_k": 5,
  "min_similarity": 0.15
}
```

The response exposes the source file, document type, chunk, page, similarity, and excerpt.

## Reference answer

`POST /api/v1/exams/{exam_id}/questions/{question_id}/reference-answer/draft` now automatically embeds the question, retrieves exam-scoped knowledge, and sends the retrieved evidence to the LLM.

`academic_context` remains optional as supplemental teacher context for backwards compatibility. It is no longer the primary knowledge source.

The response includes an `evidence` array so the faculty UI can show where the draft came from.

## Safety boundary

Uploaded documents are treated as untrusted reference material. Text inside a PDF cannot override the system prompt or become an instruction to the LLM.

The generated answer is still a draft for teacher review. It is not automatically treated as authoritative ground truth.
