from fastapi import APIRouter

from app.api.routes import auth, exam, health, knowledge_search, question_paper, reference_answer, upload

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(exam.router)
api_router.include_router(upload.router)
api_router.include_router(knowledge_search.router)
api_router.include_router(question_paper.router)
api_router.include_router(reference_answer.router)
