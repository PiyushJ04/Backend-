"""
Create the first admin account if it doesn't exist.

Run:
    python -m scripts.seed_admin
"""

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.user import User, UserRole
from app.db.session import SessionLocal, engine


def main() -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing_admin = (
            db.query(User)
            .filter(User.email == settings.first_admin_email)
            .first()
        )

        if existing_admin:
            print("Admin already exists.")
            return

        admin = User(
            username=settings.first_admin_username,
            email=str(settings.first_admin_email),
            hashed_password=hash_password(settings.first_admin_password),
            role=UserRole.ADMIN,
            is_active=True,
            must_change_password=False,
        )

        db.add(admin)
        db.commit()

        print("Default admin created successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    main()