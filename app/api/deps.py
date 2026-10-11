"""
Shared FastAPI dependencies: DB session passthrough, current-user
resolution from the JWT, and role-based access control.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import JWTError, TokenType, decode_token
from app.db.models.user import User, UserRole
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except JWTError:
        raise credentials_exception

    if payload.get("type") != TokenType.ACCESS.value:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    return user


def require_password_already_set(current_user: User = Depends(get_current_user)) -> User:
    """
    Blocks a freshly admin-created account from doing anything except
    /auth/me and /auth/change-password until they've set their own
    password. Apply this (instead of get_current_user) to every other
    protected route.
    """
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must change your temporary password before continuing",
        )
    return current_user


def require_role(*allowed_roles: UserRole):
    """
    Usage: Depends(require_role(UserRole.ADMIN))
    Stacks on top of require_password_already_set, so an inactive
    temp-password account can never reach a role-gated route either.
    """
    def _checker(current_user: User = Depends(require_password_already_set)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _checker


require_admin = require_role(UserRole.ADMIN)
