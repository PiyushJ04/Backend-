"""initial users table"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create enum only once
    role_enum = postgresql.ENUM(
        "admin",
        "paper_checker",
        "correction",
        "grievance_body",
        name="user_role",
    )
    role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),

        # IMPORTANT
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin",
                "paper_checker",
                "correction",
                "grievance_body",
                name="user_role",
                create_type=False,
            ),
            nullable=False,
        ),

        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade():
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)