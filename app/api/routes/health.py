from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health():
    return {
        "success": True,
        "service": "AI Faculty Assistant Backend",
        "version": "1.0.0",
        "status": "alive",
    }


@router.get("/ready")
async def readiness(request: Request, db: Session = Depends(get_db)):
    checks = {"database": "ok", "redis": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "unavailable"

    redis = getattr(request.app.state, "redis_client", None)
    if redis is None:
        checks["redis"] = "unavailable"
    else:
        try:
            await redis.ping()
        except Exception:
            checks["redis"] = "unavailable"

    ready = all(value == "ok" for value in checks.values())
    return {
        "success": ready,
        "status": "ready" if ready else "not_ready",
        "checks": checks,
    }
