"""phase4 question paper parsing

Revision ID: 7b1c2d3e4f50
Revises: 500659868c2d
"""

from alembic import op
import sqlalchemy as sa

revision = "7b1c2d3e4f50"
down_revision = "500659868c2d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("text_content", sa.Text(), nullable=True))
    op.create_index(
        "ix_questions_exam_id_question_no",
        "questions",
        ["exam_id", "question_no"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_questions_exam_id_question_no", table_name="questions")
    op.drop_column("documents", "text_content")
