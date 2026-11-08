"""Add categories and category-assignment tables.

Revision ID: 0005_categories
Revises: 0004_chart_of_accounts
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_categories"
down_revision = "0004_chart_of_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "categories"):
        op.create_table(
            "categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("flow", sa.Text(), nullable=False),
            sa.Column("color", sa.Text(), nullable=False, server_default="#64748b"),
            sa.Column("default_account_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.Integer(), nullable=False),
            sa.CheckConstraint("flow IN ('income', 'expense')", name="ck_categories_flow"),
            sa.ForeignKeyConstraint(["default_account_id"], ["accounts.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("name", name="uq_categories_name"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_categories_flow ON categories(flow)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_categories_default_account_id "
        "ON categories(default_account_id)"
    )

    if not bind.dialect.has_table(bind, "transactions"):
        op.create_table(
            "transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("date", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("reference", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default="posted"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.Integer(), nullable=False),
            sa.CheckConstraint("status IN ('posted', 'void')", name="ck_transactions_status"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        )

    if not bind.dialect.has_table(bind, "transaction_lines"):
        op.create_table(
            "transaction_lines",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("direction", sa.Text(), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("memo", sa.Text(), nullable=True),
            sa.Column("category_id", sa.Integer(), nullable=True),
            sa.CheckConstraint(
                "direction IN ('debit', 'credit')", name="ck_transaction_lines_direction"
            ),
            sa.CheckConstraint("amount_cents > 0", name="ck_transaction_lines_amount_pos"),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
            sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transaction_lines_transaction_id "
        "ON transaction_lines(transaction_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transaction_lines_account_id "
        "ON transaction_lines(account_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transaction_lines_category_id "
        "ON transaction_lines(category_id)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "transaction_lines"):
        op.execute("DROP INDEX IF EXISTS ix_transaction_lines_category_id")
        op.execute("DROP INDEX IF EXISTS ix_transaction_lines_account_id")
        op.execute("DROP INDEX IF EXISTS ix_transaction_lines_transaction_id")
        op.drop_table("transaction_lines")
    if bind.dialect.has_table(bind, "transactions"):
        op.drop_table("transactions")
    if bind.dialect.has_table(bind, "categories"):
        op.execute("DROP INDEX IF EXISTS ix_categories_default_account_id")
        op.execute("DROP INDEX IF EXISTS ix_categories_flow")
        op.drop_table("categories")
