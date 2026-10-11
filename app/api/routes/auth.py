from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import hash_password
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.auth import LoginRequest, Signup
from app.services.auth_service import AuthError, authenticate_user, issue_tokens

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
def signup(payload: Signup, db: Session = Depends(get_db)):
    email = str(payload.email)
    username = payload.name.strip().replace(" ", "_") or email.split("@")[0]

    existing = db.query(User).filter((User.email == email) | (User.username == username)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(payload.password),
        role=UserRole.PAPER_CHECKER,
        is_active=True,
        must_change_password=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "Signup successful",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
        },
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = authenticate_user(db, str(payload.email), payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    access_token, refresh_token = issue_tokens(user)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "must_change_password": user.must_change_password,
        },
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "must_change_password": current_user.must_change_password,
    }
