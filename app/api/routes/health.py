from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
async def health():
    return {
        "success": True,
        "service": "AI Faculty Assistant Backend",
        "version": "1.0.0",
        "status": "healthy"
    }