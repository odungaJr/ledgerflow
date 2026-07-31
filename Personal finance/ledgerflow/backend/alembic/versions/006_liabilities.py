"""Liabilities (debts) — mirrors the assets table shape

Revision ID: 006
Revises: 005
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "liabilities",
        sa.Column("id",             UUID(as_uuid=True), primary_key=True),
        sa.Column("name",           sa.String(120), nullable=False),
        sa.Column("liability_type", sa.Enum(
            "credit_card", "loan", "mortgage", "personal_debt", "other",
            name="liabilitytype",
        ), nullable=False),
        sa.Column("currency",   sa.String(10), server_default="TZS"),
        sa.Column("is_active",  sa.Boolean(), server_default=sa.true()),
        sa.Column("notes",      sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "liability_values",
        sa.Column("id",           UUID(as_uuid=True), primary_key=True),
        sa.Column("liability_id", UUID(as_uuid=True), sa.ForeignKey("liabilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value_date",   sa.Date(), nullable=False),
        sa.Column("total_value",  sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("liability_values")
    op.drop_table("liabilities")
    op.execute("DROP TYPE IF EXISTS liabilitytype")
