from fastapi import APIRouter

from app.api.routes import auth, exam, health, knowledge_search, question_paper, reference_answer, upload, phase6

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(exam.router)
api_router.include_router(upload.router)
api_router.include_router(knowledge_search.router)
api_router.include_router(question_paper.router)
api_router.include_router(reference_answer.router)
api_router.include_router(phase6.router)

from app.api.routes import student_answers, evaluation
api_router.include_router(student_answers.router)

api_router.include_router(evaluation.router)

from app.api.routes import analytics
api_router.include_router(analytics.router)

from app.api.routes import background_jobs
api_router.include_router(background_jobs.router)
