"""Initial schema — accounts, categories, transactions, budgets

Revision ID: 001
Revises:
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── accounts ──
    op.create_table(
        "accounts",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True),
        sa.Column("name",       sa.String(120), nullable=False),
        sa.Column("bank",       sa.String(120), nullable=False),
        sa.Column("currency",   sa.String(10),  server_default="TZS"),
        sa.Column("is_active",  sa.Boolean(),   server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── categories ──
    op.create_table(
        "categories",
        sa.Column("id",        UUID(as_uuid=True), primary_key=True),
        sa.Column("name",      sa.String(80),  nullable=False, unique=True),
        sa.Column("icon",      sa.String(10),  server_default="💳"),
        sa.Column("is_income", sa.Boolean(),   server_default="false"),
        sa.Column("is_system", sa.Boolean(),   server_default="true"),
    )

    # ── transactions ──
    op.create_table(
        "transactions",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id",    UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id",   UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("date",          sa.Date(),          nullable=False),
        sa.Column("description",   sa.String(300),     nullable=False),
        sa.Column("amount",        sa.Numeric(18, 2),  nullable=False),
        sa.Column("type",          sa.Enum("debit", "credit", name="transactiontype"), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 2),  nullable=True),
        sa.Column("ai_category",   sa.String(80),      nullable=True),
        sa.Column("ai_confidence", sa.Numeric(4, 3),   nullable=True),
        sa.Column("is_confirmed",  sa.Boolean(),       server_default="false"),
        sa.Column("fingerprint",   sa.String(64),      nullable=False, unique=True),
        sa.Column("notes",         sa.Text(),          nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_transactions_date",       "transactions", ["date"])
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])

    # ── budgets ──
    op.create_table(
        "budgets",
        sa.Column("id",           UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id",  UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period",       sa.Enum("monthly", "weekly", name="budgetperiod"), server_default="monthly"),
        sa.Column("limit_amount", sa.Numeric(18, 2),  nullable=False),
        sa.Column("start_date",   sa.Date(),          nullable=False),
        sa.Column("is_active",    sa.Boolean(),       server_default="true"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Seed system categories
    op.execute("""
        INSERT INTO categories (id, name, icon, is_income, is_system) VALUES
          (gen_random_uuid(), 'Salary & Wages',      '💰', true,  true),
          (gen_random_uuid(), 'Transfer In',         '📥', true,  true),
          (gen_random_uuid(), 'Food & Dining',       '🍔', false, true),
          (gen_random_uuid(), 'Transport',           '🚗', false, true),
          (gen_random_uuid(), 'Utilities',           '💡', false, true),
          (gen_random_uuid(), 'Rent & Housing',      '🏠', false, true),
          (gen_random_uuid(), 'Health & Medical',    '🏥', false, true),
          (gen_random_uuid(), 'Shopping',            '🛍️', false, true),
          (gen_random_uuid(), 'Entertainment',       '🎬', false, true),
          (gen_random_uuid(), 'Education',           '📚', false, true),
          (gen_random_uuid(), 'Savings & Investment','🏦', false, true),
          (gen_random_uuid(), 'Transfer Out',        '📤', false, true),
          (gen_random_uuid(), 'Other',               '❓', false, true)
    """)


def downgrade() -> None:
    op.drop_table("budgets")
    op.drop_index("ix_transactions_account_id", "transactions")
    op.drop_index("ix_transactions_date",        "transactions")
    op.drop_table("transactions")
    op.drop_table("categories")
    op.drop_table("accounts")
    op.execute("DROP TYPE IF EXISTS transactiontype")
    op.execute("DROP TYPE IF EXISTS budgetperiod")
