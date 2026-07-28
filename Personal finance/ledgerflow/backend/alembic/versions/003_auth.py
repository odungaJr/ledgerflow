"""Auth: users and sessions

Revision ID: 003
Revises: 002
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True),
        sa.Column("username",      sa.String(80),  nullable=False, unique=True),
        sa.Column("password_hash", sa.String(120), nullable=False),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "sessions",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",    UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_sessions_token_hash", "sessions")
    op.drop_table("sessions")
    op.drop_table("users")
