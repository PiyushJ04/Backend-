"""Phase 6 teacher-controlled baseline and marking scheme

Revision ID: a1b2c3d4e5f6
Revises: 9d3e4f5a6b72
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9d3e4f5a6b72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create PostgreSQL enum types explicitly.
    reference_status = postgresql.ENUM(
        "draft",
        "revision_requested",
        "approved",
        name="reference_answer_status_enum",
        create_type=True,
    )

    marking_status = postgresql.ENUM(
        "draft",
        "approved",
        name="marking_scheme_status_enum",
        create_type=True,
    )

    reference_status.create(bind, checkfirst=True)
    marking_status.create(bind, checkfirst=True)

    # Use separate enum objects for table columns.
    # create_type=False prevents SQLAlchemy from trying to
    # create the PostgreSQL enum again during CREATE TABLE.
    reference_status_column = postgresql.ENUM(
        "draft",
        "revision_requested",
        "approved",
        name="reference_answer_status_enum",
        create_type=False,
    )

    marking_status_column = postgresql.ENUM(
        "draft",
        "approved",
        name="marking_scheme_status_enum",
        create_type=False,
    )

    op.create_table(
        "reference_answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("key_concepts", sa.JSON(), nullable=False),
        sa.Column("expected_points", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("teacher_feedback", sa.Text(), nullable=True),
        sa.Column(
            "status",
            reference_status_column,
            nullable=False,
        ),
        sa.Column("created_by_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_reference_answers_question_id",
        "reference_answers",
        ["question_id"],
    )

    op.create_table(
        "marking_schemes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("baseline_weight", sa.Numeric(5, 2), nullable=False),
        sa.Column("factor_weight", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "status",
            marking_status_column,
            nullable=False,
        ),
        sa.Column("teacher_notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.String(length=36), nullable=False),
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
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "question_id",
            name="uq_marking_scheme_question",
        ),
    )

    op.create_index(
        "ix_marking_schemes_question_id",
        "marking_schemes",
        ["question_id"],
    )

    op.create_table(
        "marking_factors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scheme_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("weight_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scheme_id"],
            ["marking_schemes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_marking_factors_scheme_id",
        "marking_factors",
        ["scheme_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_marking_factors_scheme_id",
        table_name="marking_factors",
    )
    op.drop_table("marking_factors")

    op.drop_index(
        "ix_marking_schemes_question_id",
        table_name="marking_schemes",
    )
    op.drop_table("marking_schemes")

    op.drop_index(
        "ix_reference_answers_question_id",
        table_name="reference_answers",
    )
    op.drop_table("reference_answers")

    bind = op.get_bind()

    postgresql.ENUM(
        "draft",
        "approved",
        name="marking_scheme_status_enum",
        create_type=False,
    ).drop(bind, checkfirst=True)

    postgresql.ENUM(
        "draft",
        "revision_requested",
        "approved",
        name="reference_answer_status_enum",
        create_type=False,
    ).drop(bind, checkfirst=True)