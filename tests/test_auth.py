import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user  # noqa: F401 (kept for reference)
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.main import app

# Isolated in-memory SQLite DB just for these tests - never touches dev.db.
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_db():
    db = TestingSessionLocal()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


def _create_admin() -> None:
    db = TestingSessionLocal()
    db.add(User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("AdminPass1!"),
        role=UserRole.ADMIN,
        is_active=True,
        must_change_password=False,
    ))
    db.commit()
    db.close()


def test_login_success():
    _create_admin()
    resp = client.post(f"{settings.api_v1_prefix}/auth/login", json={"identifier": "admin", "password": "AdminPass1!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "admin"
    assert "access_token" in body and "refresh_token" in body


def test_login_wrong_password():
    _create_admin()
    resp = client.post(f"{settings.api_v1_prefix}/auth/login", json={"identifier": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_non_admin_cannot_create_users(monkeypatch):
    # A logged-in, password-already-set paper checker must not be able
    # to hit the admin-only user creation endpoint.
    db = TestingSessionLocal()
    db.add(User(
        username="checker1",
        email="checker1@example.com",
        hashed_password=hash_password("Checker1Pass!"),
        role=UserRole.PAPER_CHECKER,
        is_active=True,
        must_change_password=False,
    ))
    db.commit()
    db.close()

    login_resp = client.post(f"{settings.api_v1_prefix}/auth/login", json={"identifier": "checker1", "password": "Checker1Pass!"})
    token = login_resp.json()["access_token"]

    resp = client.post(
        f"{settings.api_v1_prefix}/admin/users",
        json={"username": "newuser", "email": "new@example.com", "role": "correction"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_admin_create_user_enqueues_email(monkeypatch):
    _create_admin()
    sent = {}

    def fake_delay(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr(
        "app.services.user_service.send_credentials_email_task.delay",
        fake_delay,
    )

    login_resp = client.post(f"{settings.api_v1_prefix}/auth/login", json={"identifier": "admin", "password": "AdminPass1!"})
    token = login_resp.json()["access_token"]

    resp = client.post(
        f"{settings.api_v1_prefix}/admin/users",
        json={"username": "grievance1", "email": "grievance1@example.com", "role": "grievance_body"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "grievance_body"
    assert body["must_change_password"] is True
    assert "hashed_password" not in body
    assert sent["to_email"] == "grievance1@example.com"


def test_forced_password_change_blocks_other_routes():
    db = TestingSessionLocal()
    db.add(User(
        username="fresh1",
        email="fresh1@example.com",
        hashed_password=hash_password("TempPass1!"),
        role=UserRole.CORRECTION,
        is_active=True,
        must_change_password=True,
    ))
    db.commit()
    db.close()

    login_resp = client.post(f"{settings.api_v1_prefix}/auth/login", json={"identifier": "fresh1", "password": "TempPass1!"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me must still work...
    me = client.get(f"{settings.api_v1_prefix}/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True

    # ...but a role-gated route must not.
    blocked = client.get(f"{settings.api_v1_prefix}/admin/users", headers=headers)
    assert blocked.status_code == 403

    changed = client.post(
        f"{settings.api_v1_prefix}/auth/change-password",
        json={"current_password": "TempPass1!", "new_password": "BrandNew1Pass"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
