"""
Login + token issuing/refresh logic. Routes call this - they never touch
the DB or jose/passlib directly.
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import (
    JWTError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.models.user import User


class AuthError(Exception):
    """Raised for any login/token failure; routes map this to HTTP 401."""


def authenticate_user(db: Session, identifier: str, password: str) -> User:
    user = (
        db.query(User)
        .filter(or_(User.username == identifier, User.email == identifier))
        .first()
    )
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Incorrect username/email or password")
    if not user.is_active:
        raise AuthError("This account has been deactivated - contact the admin")
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token = create_refresh_token(subject=user.id)
    return access_token, refresh_token


def refresh_access_token(db: Session, refresh_token: str) -> str:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise AuthError("Invalid or expired refresh token")

    if payload.get("type") != TokenType.REFRESH.value:
        raise AuthError("Not a refresh token")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if user is None or not user.is_active:
        raise AuthError("User no longer exists or is inactive")

    return create_access_token(subject=user.id, role=user.role.value)
