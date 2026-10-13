# Marklane Backend — FastAPI

This standalone repository contains the backend used by the Marklane
frontend.

## Deploy the standalone backend to Render

The API is already connected to this repository. A push to `main` triggers a
new web-service deploy. The Docker entrypoint applies Alembic migrations and
seeds the first admin before starting Uvicorn. Do not point this deploy at the
main full-stack repository.

Keep `DATABASE_URL` set to the Neon PostgreSQL connection string. Keep it
private and include Neon’s SSL option (usually `sslmode=require`). Neon must
have the `vector` extension available for the RAG migrations.

Before deploying this backend version, verify the Render web service has:

* `ENVIRONMENT=production`
* `ALLOWED_HOSTS=["backend-pl8j.onrender.com"]` (use your exact Render host,
  without `https://`)
* `JWT_SECRET_KEY` set to a private random value of at least 32 characters
* `FIRST_ADMIN_PASSWORD` set to a non-default value
* `DATABASE_URL` set to the Neon connection string

Set `CORS_ORIGINS` to the exact deployed frontend origin as a JSON array, for
example `["https://your-project.vercel.app"]`. Until then, browser requests
from the frontend will be blocked by CORS. Set `HF_TOKEN` on the API service
only if using Hugging Face features; never commit it to Git.

The API persistent disk is mounted at `/app/uploads`; uploaded exam materials
and staged student-answer PDFs are stored there. Back up the disk and database
separately.

Student-answer OCR and evaluation run as background Celery jobs. They require
a Redis-compatible broker (`CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`)
and a running Celery worker. The `render.yaml` Blueprint describes the
required Key Value and worker services. The current API stores uploaded PDFs
on its persistent disk; Render disks are not shared between services, so
background answer processing needs shared object storage before it can work
reliably across separate API and worker services. Health is available at
`/api/v1/health`; `/api/v1/health/ready` also checks database and Redis
connectivity.

## Completed phases

- Phase 1 — Foundation / authentication
- Phase 2 — Exam management
- Phase 3 — Knowledge document ingestion foundation
- Phase 4 — Deterministic theoretical question-paper ingestion and validation
- Phase 5A — Hugging Face LLM abstraction + structured Reference Answer Agent
- Phase 5B — Real BGE embeddings + pgvector retrieval + grounded evidence

## Phase 5A / 5B

The reference-answer pipeline is now grounded in exam-scoped faculty knowledge:

```text
Question
   |
   v
BAAI/bge-small-en-v1.5 embedding
   |
   v
PostgreSQL + pgvector cosine retrieval
   |
   v
Relevant syllabus / notes / sample-answer chunks
   |
   v
ReferenceAnswerAgent
   |
   v
Hugging Face LLM
   |
   v
Teacher-reviewable reference answer + evidence
```

Phase 5B stores 384-dimensional real embeddings, preserves source file and PDF page metadata, uses an HNSW cosine index, and returns retrieved evidence alongside the generated answer. Uploaded document text is treated as untrusted reference material; instructions inside documents are not treated as system instructions.

### Hugging Face configuration

```env
HF_TOKEN=hf_...
HF_PROVIDER=auto
LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
LLM_TIMEOUT_SECONDS=60
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
EMBEDDING_TIMEOUT_SECONDS=60
RAG_TOP_K=5
RAG_MIN_SIMILARITY=0.15
```

### Phase 5B APIs

Knowledge upload expects multipart field `files`:

```bash
curl -X POST "http://localhost:8000/api/v1/exams/$EXAM_ID/knowledge" \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@/e/Projects/PBL/test_data/oop_notes.pdf" \
  -F "type=theory_notes"
```

Test retrieval directly:

```bash
curl -X POST "http://localhost:8000/api/v1/exams/$EXAM_ID/knowledge/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"Explain abstraction and encapsulation", "top_k":5}'
```

Generate a grounded reference answer:

```bash
curl -X POST "http://localhost:8000/api/v1/exams/$EXAM_ID/questions/$QUESTION_ID/reference-answer/draft" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"top_k":5}'
```

The `academic_context` field remains optional as supplemental teacher context for backwards compatibility; retrieval from the exam knowledge base is now automatic.
