"""
Admin-side user management: creating handler accounts (paper checker,
correction, grievance body) and the forced first-login password change.
Routes call this - they never touch the DB session's add/commit directly.
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import generate_temp_password, hash_password, verify_password
from app.db.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.workers.email_tasks import send_credentials_email_task


class UserServiceError(Exception):
    """Raised for any user-management failure; routes map this to an HTTP error."""


def create_handler_user(db: Session, payload: UserCreate, created_by: User) -> User:
    """
    Central-body flow: admin supplies username/email/role only. We
    generate the temp password, store its hash, and fire off the
    first-time credentials email asynchronously via Celery so the
    admin's request returns immediately.
    """
    temp_password = generate_temp_password()

    user = User(
        username=payload.username,
        email=payload.email,
        role=payload.role,
        hashed_password=hash_password(temp_password),
        must_change_password=True,
        is_active=True,
        created_by_id=created_by.id,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise UserServiceError("A user with that username or email already exists")
    db.refresh(user)

    send_credentials_email_task.delay(
        to_email=user.email,
        username=user.username,
        temp_password=temp_password,
        role=user.role.value,
    )

    return user


def set_active_status(db: Session, user: User, is_active: bool) -> User:
    if user.role == UserRole.ADMIN:
        raise UserServiceError("Admin accounts cannot be deactivated through this endpoint")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> User:
    if not verify_password(current_password, user.hashed_password):
        raise UserServiceError("Current password is incorrect")
    if verify_password(new_password, user.hashed_password):
        raise UserServiceError("New password must be different from the current password")

    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    db.commit()
    db.refresh(user)
    return user
