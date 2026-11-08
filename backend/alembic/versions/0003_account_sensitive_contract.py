"""Add encrypted account-sensitive storage and active key metadata.

Revision ID: 0003_account_sensitive_contract
Revises: 0002_users_last_login
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_account_sensitive_contract"
down_revision = "0002_users_last_login"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), nullable=False, primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("value_type", sa.Text(), nullable=False, server_default="str"),
        sa.Column("updated_at", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "account_sensitive",
        sa.Column("account_id", sa.Integer(), primary_key=True),
        sa.Column("account_number_enc", sa.LargeBinary(), nullable=True),
        sa.Column("routing_transit_enc", sa.LargeBinary(), nullable=True),
        sa.Column("transfer_numbers_enc", sa.LargeBinary(), nullable=True),
        sa.Column("notes_enc", sa.LargeBinary(), nullable=True),
        sa.Column("key_id", sa.Text(), nullable=False, server_default="v1"),
    )
    op.execute(
        "INSERT INTO settings(key, value, value_type, updated_at) "
        "VALUES ('active_key_id', 'v1', 'str', 0) "
        "ON CONFLICT(key) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("account_sensitive")
    op.drop_table("settings")
