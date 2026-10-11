
from fastapi import FastAPI
from app.api.routes.auth import router
app=FastAPI(title="Faculty Auth")
app.include_router(router,prefix="/api/v1/auth",tags=["auth"])
