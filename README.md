# AI Faculty Assistant — FastAPI Backend

Current milestone: **Phase 5B — Grounded RAG Reference Answer Pipeline**.

## Deploy the standalone backend to Render

This folder is deployable as its own repository. Push the contents of
`backend/` to a Git repository, then in Render choose **New > Blueprint** and
connect that repository. Render reads `render.yaml` to create the API, a
Celery email worker, and a Redis-compatible Key Value instance. The Docker
image runs Alembic migrations and creates the initial admin on API startup.
The PostgreSQL database is hosted separately on Neon.

Set `DATABASE_URL` to your Neon PostgreSQL connection string on both the API
and worker services. Keep the URL secret; include Neon’s required SSL setting
(usually `sslmode=require`). The app accepts Neon’s `postgresql://` URL format.
The initial deployment may ask for `DATABASE_URL` separately for each service.

Before the first deploy, edit `render.yaml` and replace
`admin@example.com` with the email address for the initial admin. Render
generates `JWT_SECRET_KEY` and `FIRST_ADMIN_PASSWORD`; retrieve the generated
admin password from the API service's environment settings and change it after
the first login.

After the services are created:

1. Set the API service's `CORS_ORIGINS` to a JSON array containing the exact
   deployed frontend origin, for example `["https://your-frontend.onrender.com"]`.
   The default empty list intentionally does not allow browser origins.
2. Configure the worker's SMTP settings (`SMTP_HOST`, `SMTP_USERNAME`,
   `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL`) to enable first-time credential
   emails.
3. Set `HF_TOKEN` on the API service if you use the Hugging Face answer and
   embedding features.
4. Check the API service at `/api/v1/health`. Interactive API docs are disabled
   when `ENVIRONMENT=production`.

The API's persistent disk is mounted at `/app/uploads`, so uploaded PDFs
survive service restarts and deploys. Back up this disk and the database
separately. Render persistent disks and non-free service plans are required by
this Blueprint; review Render's current pricing before deploying.

For a manual Render setup, use the Docker runtime with this folder as the
service root, `Dockerfile` as the Dockerfile, and `/api/v1/health` as the
health-check path. Set `ENVIRONMENT=production`, a strong `JWT_SECRET_KEY`,
`DATABASE_URL`, `CORS_ORIGINS`, and secure `FIRST_ADMIN_USERNAME`,
`FIRST_ADMIN_EMAIL`, and `FIRST_ADMIN_PASSWORD` values before the first
startup; attach a persistent disk at `/app/uploads`. Run a separate worker with command
`celery -A app.core.celery_app.celery_app worker --loglevel=info` and
`RUN_MIGRATIONS=false`, and configure both services with the same Redis URL
for `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.

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
