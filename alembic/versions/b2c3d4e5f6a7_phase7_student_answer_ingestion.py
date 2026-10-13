"""Phase 7 student answer-sheet ingestion

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create the PostgreSQL enum explicitly.
    answer_sheet_status = postgresql.ENUM(
        "ingested",
        "ocr_processed",
        "segmented",
        "ready",
        "failed",
        name="answer_sheet_status_enum",
        create_type=True,
    )

    answer_sheet_status.create(bind, checkfirst=True)

    # Use a separate enum object for the table column.
    # This prevents SQLAlchemy from attempting to create
    # answer_sheet_status_enum again during CREATE TABLE.
    answer_sheet_status_column = postgresql.ENUM(
        "ingested",
        "ocr_processed",
        "segmented",
        "ready",
        "failed",
        name="answer_sheet_status_enum",
        create_type=False,
    )

    op.create_table(
        "student_answer_sheets",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("exam_id", sa.String(36), nullable=False),
        sa.Column("student_identifier", sa.String(120), nullable=False),
        sa.Column("original_file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            answer_sheet_status_column,
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exam_id",
            "student_identifier",
            name="uq_answer_sheet_exam_student",
        ),
    )

    op.create_index(
        "ix_student_answer_sheets_exam_id",
        "student_answer_sheets",
        ["exam_id"],
    )

    op.create_index(
        "ix_student_answer_sheets_student_identifier",
        "student_answer_sheets",
        ["student_identifier"],
    )

    op.create_index(
        "ix_student_answer_sheets_sha256",
        "student_answer_sheets",
        ["sha256"],
    )

    op.create_table(
        "student_answers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("answer_sheet_id", sa.String(36), nullable=False),
        sa.Column("question_id", sa.String(36), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["answer_sheet_id"],
            ["student_answer_sheets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "answer_sheet_id",
            "question_id",
            name="uq_student_answer_sheet_question",
        ),
    )

    op.create_index(
        "ix_student_answers_answer_sheet_id",
        "student_answers",
        ["answer_sheet_id"],
    )

    op.create_index(
        "ix_student_answers_question_id",
        "student_answers",
        ["question_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_student_answers_question_id",
        table_name="student_answers",
    )

    op.drop_index(
        "ix_student_answers_answer_sheet_id",
        table_name="student_answers",
    )

    op.drop_table("student_answers")

    op.drop_index(
        "ix_student_answer_sheets_sha256",
        table_name="student_answer_sheets",
    )

    op.drop_index(
        "ix_student_answer_sheets_student_identifier",
        table_name="student_answer_sheets",
    )

    op.drop_index(
        "ix_student_answer_sheets_exam_id",
        table_name="student_answer_sheets",
    )

    op.drop_table("student_answer_sheets")

    bind = op.get_bind()

    postgresql.ENUM(
        "ingested",
        "ocr_processed",
        "segmented",
        "ready",
        "failed",
        name="answer_sheet_status_enum",
        create_type=False,
    ).drop(bind, checkfirst=True)