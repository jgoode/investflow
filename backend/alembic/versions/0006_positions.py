"""Add brokerage position tables with avg-cost accounting.

Revision ID: 0006_positions
Revises: 0005_categories
Create Date: 2026-11-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_positions"
down_revision = "0005_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "positions"):
        op.create_table(
            "positions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("ticker", sa.Text(), nullable=False),
            sa.Column("quantity_q4", sa.Integer(), nullable=False),
            sa.Column("avg_cost_q4", sa.Integer(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default="open"),
            sa.Column("realized_gain_loss_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_price_q4", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_trade_date", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.Integer(), nullable=False),
            sa.CheckConstraint("quantity_q4 >= 0", name="ck_positions_quantity_nonnegative"),
            sa.CheckConstraint("status IN ('open', 'closed')", name="ck_positions_status"),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("account_id", "ticker", name="uq_positions_account_ticker"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_positions_account_id ON positions(account_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_positions_account_status ON positions(account_id, status)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_positions_ticker ON positions(ticker)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "positions"):
        op.execute("DROP INDEX IF EXISTS ix_positions_ticker")
        op.execute("DROP INDEX IF EXISTS ix_positions_account_status")
        op.execute("DROP INDEX IF EXISTS ix_positions_account_id")
        op.drop_table("positions")
