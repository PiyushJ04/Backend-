"""Phase 8 answer evaluation engine
Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Explicitly create the PostgreSQL enum once.
    evaluation_run_status = postgresql.ENUM(
        "running",
        "completed",
        "failed",
        name="evaluation_run_status_enum",
        create_type=True,
    )

    evaluation_run_status.create(bind, checkfirst=True)

    # Use a separate enum object for the table column so SQLAlchemy
    # does not attempt to CREATE TYPE again.
    evaluation_run_status_column = postgresql.ENUM(
        "running",
        "completed",
        "failed",
        name="evaluation_run_status_enum",
        create_type=False,
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("answer_sheet_id", sa.String(36), nullable=False),
        sa.Column(
            "status",
            evaluation_run_status_column,
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["answer_sheet_id"],
            ["student_answer_sheets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_evaluation_runs_answer_sheet_id",
        "evaluation_runs",
        ["answer_sheet_id"],
    )

    op.create_table(
        "answer_evaluations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("answer_sheet_id", sa.String(36), nullable=False),
        sa.Column("question_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("baseline_ratio", sa.Numeric(6, 4), nullable=False),
        sa.Column("baseline_points", sa.Numeric(8, 2), nullable=False),
        sa.Column("factor_points", sa.Numeric(8, 2), nullable=False),
        sa.Column("total_points", sa.Numeric(8, 2), nullable=False),
        sa.Column("max_marks", sa.Numeric(8, 2), nullable=False),
        sa.Column("academic_feedback", sa.Text(), nullable=False),
        sa.Column("matched_points", sa.JSON(), nullable=False),
        sa.Column("missing_points", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "answer_sheet_id",
            "question_id",
            name="uq_answer_evaluation_sheet_question",
        ),
    )

    op.create_index(
        "ix_answer_evaluations_answer_sheet_id",
        "answer_evaluations",
        ["answer_sheet_id"],
    )

    op.create_index(
        "ix_answer_evaluations_question_id",
        "answer_evaluations",
        ["question_id"],
    )

    op.create_index(
        "ix_answer_evaluations_run_id",
        "answer_evaluations",
        ["run_id"],
    )

    op.create_table(
        "factor_scores",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("evaluation_id", sa.String(36), nullable=False),
        sa.Column("factor_id", sa.String(36), nullable=False),
        sa.Column("ratio", sa.Numeric(6, 4), nullable=False),
        sa.Column("points", sa.Numeric(8, 2), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["answer_evaluations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["factor_id"],
            ["marking_factors.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_factor_scores_evaluation_id",
        "factor_scores",
        ["evaluation_id"],
    )

    op.create_index(
        "ix_factor_scores_factor_id",
        "factor_scores",
        ["factor_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(
        "ix_factor_scores_factor_id",
        table_name="factor_scores",
    )

    op.drop_index(
        "ix_factor_scores_evaluation_id",
        table_name="factor_scores",
    )

    op.drop_table("factor_scores")

    op.drop_index(
        "ix_answer_evaluations_run_id",
        table_name="answer_evaluations",
    )

    op.drop_index(
        "ix_answer_evaluations_question_id",
        table_name="answer_evaluations",
    )

    op.drop_index(
        "ix_answer_evaluations_answer_sheet_id",
        table_name="answer_evaluations",
    )

    op.drop_table("answer_evaluations")

    op.drop_index(
        "ix_evaluation_runs_answer_sheet_id",
        table_name="evaluation_runs",
    )

    op.drop_table("evaluation_runs")

    # Drop the PostgreSQL enum after its dependent table is gone.
    evaluation_run_status = postgresql.ENUM(
        "running",
        "completed",
        "failed",
        name="evaluation_run_status_enum",
        create_type=False,
    )

    evaluation_run_status.drop(bind, checkfirst=True)