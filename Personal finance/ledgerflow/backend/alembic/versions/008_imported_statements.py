"""Imported statements — dedupe whole-file re-uploads

Revision ID: 008
Revises: 007
Create Date: 2026-08-02

Tracks a hash of every successfully-parsed statement file per (user,
account), so re-uploading the exact same file is detected and skipped
before it's even parsed — distinct from the existing per-transaction
fingerprint dedupe, which only catches individual duplicate rows, not "did
I already upload this file".
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "imported_statements",
        sa.Column("id",                UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",           UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id",        UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_hash",         sa.String(64), nullable=False),   # sha256 hex digest of the raw file bytes
        sa.Column("filename",          sa.String(255), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("imported_at",       sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_unique_constraint(
        "uq_imported_statements_account_id_file_hash",
        "imported_statements", ["account_id", "file_hash"],
    )
    op.create_index(
        "ix_imported_statements_user_id", "imported_statements", ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_imported_statements_user_id", table_name="imported_statements")
    op.drop_constraint("uq_imported_statements_account_id_file_hash", "imported_statements", type_="unique")
    op.drop_table("imported_statements")
