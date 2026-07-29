"""Account manual balances

Revision ID: 004
Revises: 003
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("manual_balance", sa.Numeric(18, 2), nullable=True))
    op.add_column("accounts", sa.Column("manual_balance_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "manual_balance_date")
    op.drop_column("accounts", "manual_balance")
