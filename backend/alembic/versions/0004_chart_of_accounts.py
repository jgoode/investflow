"""Add the chart-of-accounts model and seed metadata.

Revision ID: 0004_chart_of_accounts
Revises: 0003_account_sensitive_contract
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_chart_of_accounts"
down_revision = "0003_account_sensitive_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "accounts"):
        op.create_table(
            "accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("type", sa.Text(), nullable=False),
            sa.Column("subtype", sa.Text(), nullable=False, server_default="other"),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("institution", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("last4", sa.Text(), nullable=True),
            sa.Column("is_archived", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_investment", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("code", name="uq_accounts_code"),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_accounts_parent_id ON accounts(parent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_accounts_type ON accounts(type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_accounts_is_archived ON accounts(is_archived)")

    if not bind.dialect.has_table(bind, "seed_meta"):
        op.create_table(
            "seed_meta",
            sa.Column("name", sa.Text(), nullable=False, primary_key=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("applied_at", sa.Integer(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "accounts"):
        op.execute("DROP INDEX IF EXISTS ix_accounts_is_archived")
        op.execute("DROP INDEX IF EXISTS ix_accounts_type")
        op.execute("DROP INDEX IF EXISTS ix_accounts_parent_id")
        if bind.dialect.has_table(bind, "seed_meta"):
            op.drop_table("seed_meta")
        op.drop_table("accounts")
