import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.student_answer_service import StudentAnswerService


def test_production_requires_explicit_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            jwt_secret_key="change-me-to-a-real-random-secret",
            first_admin_password="A-real-password-123!",
        )


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            jwt_secret_key="too-short",
            first_admin_password="A-real-password-123!",
        )


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            jwt_secret_key="x" * 40,
            cors_origins=["*"],
            first_admin_password="A-real-password-123!",
        )


def test_student_answer_zip_limits_are_explicit():
    assert StudentAnswerService.MAX_ZIP_BYTES == 100 * 1024 * 1024
    assert StudentAnswerService.MAX_FILES == 200
    assert StudentAnswerService.MAX_UNCOMPRESSED_BYTES == 500 * 1024 * 1024
    assert StudentAnswerService.MAX_SINGLE_PDF_BYTES == 25 * 1024 * 1024
