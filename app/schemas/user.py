from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from app.db.models.user import UserRole

_ASSIGNABLE_ROLES = {UserRole.PAPER_CHECKER, UserRole.CORRECTION, UserRole.GRIEVANCE_BODY}


class UserCreate(BaseModel):
    """
    What the admin submits to create a new handler account. No password
    field on purpose - the backend generates a temp password and emails
    it; the admin only ever supplies identity + role.
    """
    username: str
    email: EmailStr
    role: UserRole

    @field_validator("role")
    @classmethod
    def _only_assignable_roles(cls, v: UserRole) -> UserRole:
        if v not in _ASSIGNABLE_ROLES:
            raise ValueError(
                f"role must be one of {[r.value for r in _ASSIGNABLE_ROLES]}; "
                "admin accounts cannot be created through this endpoint"
            )
        return v

    @field_validator("username")
    @classmethod
    def _username_format(cls, v: str) -> str:
        v = v.strip()
        if not (3 <= len(v) <= 64):
            raise ValueError("username must be between 3 and 64 characters")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: EmailStr
    role: UserRole
    is_active: bool
    must_change_password: bool
    created_at: datetime


class UserUpdateStatus(BaseModel):
    """Admin toggling a handler account on/off."""
    is_active: bool
