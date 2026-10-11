"""
Password hashing + JWT issuing/verification.
This is the ONE place token/hash logic lives - services import from here,
they never call jose/passlib directly.
"""
import secrets
import string
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_temp_password(length: int | None = None) -> str:
    """
    Generates a random, human-typeable temporary password for
    admin-created users (sent to them by email on first creation).
    Guarantees at least one lower/upper/digit/symbol character.
    """
    length = length or settings.temp_password_length
    alphabet = string.ascii_letters + string.digits
    symbols = "!@#$%^&*"

    while True:
        pwd = "".join(secrets.choice(alphabet + symbols) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in symbols for c in pwd)
        ):
            return pwd


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    to_encode: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject=subject,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims={"role": role},
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject=subject,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Raises jose.JWTError if invalid/expired - caller decides HTTP response."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


__all__ = [
    "hash_password",
    "verify_password",
    "generate_temp_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "TokenType",
    "JWTError",
]
