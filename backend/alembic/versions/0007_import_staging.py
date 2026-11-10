"""Import staging tables for FR-IMP-1 (portfolio CSV import).

Revision ID: 0007_import_staging
Revises: 0006_positions
Create Date: 2026-11-10

- import_mappings: saved column-mapping templates (starter + user-defined).
- import_batches: one row per committed/failed import (counts + status only;
  raw CSV is never persisted wholesale, per docs/02 §3.1).
- import_rows: per-row registration carrying the dedupe row-hash and status
  (posted/duplicate/removed) — the trade dedupe registry (AC-IMP1c).
Only failure rows persist detail payloads, never full source rows.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_import_staging"
down_revision = "0006_positions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "import_mappings"):
        op.create_table(
            "import_mappings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("kind", sa.Text(), nullable=False),
            sa.Column("columns_json", sa.Text(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.UniqueConstraint("name", name="uq_import_mappings_name"),
        )
    if not bind.dialect.has_table(bind, "import_batches"):
        op.create_table(
            "import_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", sa.Text(), nullable=False),
            sa.Column("file_name", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("counts_json", sa.Text(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.CheckConstraint(
                "kind IN ('positions', 'trades', 'price_history')", name="ck_import_batches_kind"
            ),
            sa.CheckConstraint(
                "status IN ('committed', 'failed')", name="ck_import_batches_status"
            ),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_import_batches_kind ON import_batches(kind, status)")
    if not bind.dialect.has_table(bind, "import_rows"):
        op.create_table(
            "import_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("batch_id", sa.Integer(), nullable=False),
            sa.Column("row_index", sa.Integer(), nullable=False),
            sa.Column("row_hash", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("detail_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
            sa.CheckConstraint(
                "status IN ('posted', 'duplicate', 'removed')", name="ck_import_rows_status"
            ),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_import_rows_batch ON import_rows(batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_import_rows_hash ON import_rows(row_hash)")


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_import_rows_hash")
    op.execute("DROP INDEX IF EXISTS ix_import_rows_batch")
    if bind.dialect.has_table(bind, "import_rows"):
        op.drop_table("import_rows")
    op.execute("DROP INDEX IF EXISTS ix_import_batches_kind")
    if bind.dialect.has_table(bind, "import_batches"):
        op.drop_table("import_batches")
    if bind.dialect.has_table(bind, "import_mappings"):
        op.drop_table("import_mappings")
