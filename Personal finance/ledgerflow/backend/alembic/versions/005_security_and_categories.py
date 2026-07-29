"""Login lockout, idle session timeout, and additional default categories

Revision ID: 005
Revises: 004
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "sessions",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Round out the default category list — seeded via ON CONFLICT DO NOTHING
    # since `name` is unique and this migration may run against a DB that
    # already has some of these from manual testing.
    op.execute("""
        INSERT INTO categories (id, name, icon, is_income, is_system) VALUES
          (gen_random_uuid(), 'Other Income',       '💵', true,  true),
          (gen_random_uuid(), 'Subscriptions',       '🔁', false, true),
          (gen_random_uuid(), 'Insurance',           '🛡️', false, true),
          (gen_random_uuid(), 'Fees & Charges',      '💸', false, true),
          (gen_random_uuid(), 'Travel',              '✈️', false, true),
          (gen_random_uuid(), 'Gifts & Donations',   '🎁', false, true),
          (gen_random_uuid(), 'Personal Care',       '🧴', false, true),
          (gen_random_uuid(), 'Family & Kids',       '👶', false, true),
          (gen_random_uuid(), 'Business Expenses',   '💼', false, true),
          (gen_random_uuid(), 'Taxes',               '🧾', false, true)
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM categories WHERE name IN (
          'Other Income', 'Subscriptions', 'Insurance', 'Fees & Charges', 'Travel',
          'Gifts & Donations', 'Personal Care', 'Family & Kids', 'Business Expenses', 'Taxes'
        )
    """)
    op.drop_column("sessions", "last_seen_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
