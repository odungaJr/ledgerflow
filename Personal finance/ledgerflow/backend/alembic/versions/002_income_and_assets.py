"""Income tracker and assets tracker

Revision ID: 002
Revises: 001
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── income_entries ──
    op.create_table(
        "income_entries",
        sa.Column("id",                UUID(as_uuid=True), primary_key=True),
        sa.Column("series_id",         UUID(as_uuid=True), sa.ForeignKey("income_entries.id"), nullable=True),
        sa.Column("category_id",       UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("source",            sa.String(120),     nullable=False),
        sa.Column("expected_amount",   sa.Numeric(18, 2),  nullable=False),
        sa.Column("expected_date",     sa.Date(),          nullable=False),
        sa.Column("received_amount",   sa.Numeric(18, 2),  nullable=False, server_default="0"),
        sa.Column("received_date",     sa.Date(),          nullable=True),
        sa.Column("is_recurring",      sa.Boolean(),       server_default="false"),
        sa.Column("recurrence_period", sa.Enum("monthly", "weekly", name="recurrenceperiod"), nullable=True),
        sa.Column("notes",             sa.Text(),          nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_income_entries_expected_date", "income_entries", ["expected_date"])
    op.create_index("ix_income_entries_series_id",     "income_entries", ["series_id"])

    # ── assets ──
    op.create_table(
        "assets",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True),
        sa.Column("name",       sa.String(120), nullable=False),
        sa.Column("asset_type", sa.Enum("cash", "stocks", "bonds", "real_estate", "vehicle", "other", name="assettype"), nullable=False),
        sa.Column("quantity",   sa.Numeric(18, 4), nullable=True),
        sa.Column("currency",   sa.String(10),  server_default="TZS"),
        sa.Column("is_active",  sa.Boolean(),   server_default="true"),
        sa.Column("notes",      sa.Text(),      nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── asset_values ──
    op.create_table(
        "asset_values",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id",    UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value_date",  sa.Date(), nullable=False),
        sa.Column("unit_value",  sa.Numeric(18, 4), nullable=True),
        sa.Column("total_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_asset_values_asset_id_value_date", "asset_values", ["asset_id", "value_date"])


def downgrade() -> None:
    op.drop_index("ix_asset_values_asset_id_value_date", "asset_values")
    op.drop_table("asset_values")
    op.drop_table("assets")
    op.execute("DROP TYPE IF EXISTS assettype")

    op.drop_index("ix_income_entries_series_id",     "income_entries")
    op.drop_index("ix_income_entries_expected_date", "income_entries")
    op.drop_table("income_entries")
    op.execute("DROP TYPE IF EXISTS recurrenceperiod")
