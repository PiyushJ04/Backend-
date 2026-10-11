"""add structured question metadata for phase 4

Revision ID: 8c2d3e4f5a61
Revises: 7b1c2d3e4f50
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8c2d3e4f5a61"
down_revision: Union[str, None] = "7b1c2d3e4f50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("section", sa.String(length=10), nullable=True))
    question_type_enum = sa.Enum(
        "mcq", "very_short", "short", "long", "theoretical",
        name="question_type_enum",
    )
    question_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "questions",
        sa.Column("question_type", question_type_enum, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questions", "question_type")
    sa.Enum(
        "mcq", "very_short", "short", "long", "theoretical",
        name="question_type_enum",
    ).drop(op.get_bind(), checkfirst=True)
    op.drop_column("questions", "section")
