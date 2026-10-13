"""Store structured reference answers per sub-question.

Revision ID: 1a2b3c4d5e6f
Revises: f6a7b8c9d0e1
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reference_answers",
        sa.Column("sub_answers", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.alter_column("reference_answers", "sub_answers", server_default=None)


def downgrade() -> None:
    op.drop_column("reference_answers", "sub_answers")
