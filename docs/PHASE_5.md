# Phase 5 — AI Reference Answer Pipeline

Phase 5 is implemented in two increments.

## Phase 5A — LLM foundation

- Hugging Face `InferenceClient` abstraction.
- Configurable chat model/provider.
- Structured `ReferenceAnswerDraft` validation.
- Teacher-reviewable ideal answer generation.

## Phase 5B — Grounded RAG

- Real `BAAI/bge-small-en-v1.5` 384-dimensional embeddings.
- Page-aware PDF chunking.
- PostgreSQL `pgvector` storage.
- HNSW cosine index.
- Exam-scoped similarity retrieval.
- Source file/page evidence in API responses.
- Automatic retrieval before reference-answer generation.
- Optional manual context retained only as supplemental teacher context.

The zero-vector embedding implementation is removed from the production path.

See `docs/PHASE_5B.md` for the complete pipeline and API examples.
