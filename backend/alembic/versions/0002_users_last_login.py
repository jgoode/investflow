"""Add users.last_login_at for ITER-03.

Revision ID: 0002_users_last_login
Revises: 0001_users_auth_core
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_users_last_login"
down_revision = "0001_users_auth_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.Integer(), nullable=True))
    op.create_index("ix_users_last_login_at", "users", ["last_login_at"])


def downgrade() -> None:
    op.drop_index("ix_users_last_login_at", table_name="users")
    op.drop_column("users", "last_login_at")
