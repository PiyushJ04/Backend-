from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.user import UserCreate, UserOut, UserUpdateStatus
from app.services import user_service
from app.services.user_service import UserServiceError

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    Central-body creation: admin sets username/email/role only. A temp
    password is generated server-side and emailed to the user (async,
    via Celery) - it is never returned in this response.
    """
    try:
        return user_service.create_handler_user(db, payload, created_by=current_admin)
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/users", response_model=List[UserOut])
def list_users(role: UserRole | None = None, db: Session = Depends(get_db)):
    query = db.query(User).filter(User.role != UserRole.ADMIN)
    if role is not None:
        query = query.filter(User.role == role)
    return query.order_by(User.created_at.desc()).all()


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/users/{user_id}/status", response_model=UserOut)
def update_user_status(user_id: str, payload: UserUpdateStatus, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        return user_service.set_active_status(db, user, payload.is_active)
    except UserServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
