"""Add background job type for asynchronous student-answer ingestion.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

from typing import Sequence, Union
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE background_job_type_enum ADD VALUE IF NOT EXISTS 'ingest_answers'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove an enum value in-place. The value is
    # harmless for older rows because this migration is only used by the
    # upgraded application. A downgrade should therefore be handled by a
    # full database migration/restore rather than destructive enum surgery.
    pass
