"""
Declarative Base for all SQLAlchemy models.

Keep this module free of model imports to avoid circular import loops when
app.db.models.user imports Base from here.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
