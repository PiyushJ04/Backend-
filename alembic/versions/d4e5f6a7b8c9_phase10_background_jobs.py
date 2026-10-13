"""Phase 10 durable background job tracking
Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ---------------------------------------------------------
    # Create PostgreSQL ENUM types explicitly.
    # ---------------------------------------------------------

    background_job_type = postgresql.ENUM(
        "evaluate_sheet",
        "evaluate_exam",
        name="background_job_type_enum",
        create_type=True,
    )

    background_job_status = postgresql.ENUM(
        "queued",
        "running",
        "completed",
        "failed",
        name="background_job_status_enum",
        create_type=True,
    )

    background_job_type.create(bind, checkfirst=True)
    background_job_status.create(bind, checkfirst=True)

    # ---------------------------------------------------------
    # Use create_type=False for table columns.
    # This prevents SQLAlchemy from attempting to create
    # the ENUM types a second time.
    # ---------------------------------------------------------

    background_job_type_column = postgresql.ENUM(
        "evaluate_sheet",
        "evaluate_exam",
        name="background_job_type_enum",
        create_type=False,
    )

    background_job_status_column = postgresql.ENUM(
        "queued",
        "running",
        "completed",
        "failed",
        name="background_job_status_enum",
        create_type=False,
    )

    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("exam_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),

        sa.Column(
            "job_type",
            background_job_type_column,
            nullable=False,
        ),

        sa.Column(
            "status",
            background_job_status_column,
            nullable=False,
        ),

        sa.Column("sheet_id", sa.String(36), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),

        sa.Column(
            "progress_total",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "progress_completed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["sheet_id"],
            ["student_answer_sheets.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_background_jobs_exam_id",
        "background_jobs",
        ["exam_id"],
    )

    op.create_index(
        "ix_background_jobs_requested_by",
        "background_jobs",
        ["requested_by"],
    )

    op.create_index(
        "ix_background_jobs_status",
        "background_jobs",
        ["status"],
    )

    op.create_index(
        "ix_background_jobs_sheet_id",
        "background_jobs",
        ["sheet_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(
        "ix_background_jobs_sheet_id",
        table_name="background_jobs",
    )

    op.drop_index(
        "ix_background_jobs_status",
        table_name="background_jobs",
    )

    op.drop_index(
        "ix_background_jobs_requested_by",
        table_name="background_jobs",
    )

    op.drop_index(
        "ix_background_jobs_exam_id",
        table_name="background_jobs",
    )

    op.drop_table("background_jobs")

    # Drop ENUMs only after the table using them has been removed.
    background_job_status = postgresql.ENUM(
        "queued",
        "running",
        "completed",
        "failed",
        name="background_job_status_enum",
        create_type=False,
    )

    background_job_type = postgresql.ENUM(
        "evaluate_sheet",
        "evaluate_exam",
        name="background_job_type_enum",
        create_type=False,
    )

    background_job_status.drop(bind, checkfirst=True)
    background_job_type.drop(bind, checkfirst=True)