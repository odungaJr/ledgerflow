"""Multi-tenant data isolation — user_id on every domain table

Revision ID: 007
Revises: 006
Create Date: 2026-07-31

Adds a `user_id` owner column to every domain table (accounts, categories,
transactions, budgets, income_entries, assets, asset_values, liabilities,
liability_values) so each registered user's data is fully private instead of
one shared global dataset. Existing rows are backfilled to whichever user
already exists (there is exactly one, pre-migration — this app was
single-tenant until now).

Also fixes two constraints that were global and would otherwise let one
user's data collide with another's once categories/transactions are private:
`categories.name` and `transactions.fingerprint` move from a table-wide
UNIQUE to UNIQUE-per-user. Adds a new UNIQUE(series_id, expected_date) on
income_entries to close a pre-existing (single-tenant-era) race in
recurring-income occurrence generation.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

_TABLES = [
    "accounts", "categories", "transactions", "budgets", "income_entries",
    "assets", "asset_values", "liabilities", "liability_values",
]


def upgrade() -> None:
    # 1. Add a nullable user_id to every domain table.
    for table in _TABLES:
        op.add_column(table, sa.Column("user_id", UUID(as_uuid=True), nullable=True))

    # 2. Backfill every existing row to the one pre-existing user. Runs as
    # part of the same deploy that removes the auth.py bootstrap lock (see
    # docker-entrypoint.sh: migrations always run before the app starts
    # serving), so there's no window where a second user could register
    # before this backfill completes.
    for table in _TABLES:
        op.execute(f"""
            UPDATE {table}
            SET user_id = (SELECT id FROM users ORDER BY created_at LIMIT 1)
            WHERE user_id IS NULL
        """)

    # 3. Now safe to enforce NOT NULL + FK + index on every table.
    for table in _TABLES:
        op.alter_column(table, "user_id", nullable=False)
        op.create_foreign_key(
            f"{table}_user_id_fkey", table, "users",
            ["user_id"], ["id"], ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])

    # 4. Categories and transaction fingerprints were unique app-wide;
    # under per-user data they must be unique per-user instead.
    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.create_unique_constraint("uq_categories_user_id_name", "categories", ["user_id", "name"])

    op.drop_constraint("transactions_fingerprint_key", "transactions", type_="unique")
    op.create_unique_constraint(
        "uq_transactions_user_id_fingerprint", "transactions", ["user_id", "fingerprint"],
    )

    # 5. Close a pre-existing race in ensure_recurring_occurrences: nothing
    # stopped two concurrent calls from both inserting an occurrence for the
    # same series+date. NULLs (every non-recurring entry's series_id) don't
    # collide under a Postgres UNIQUE constraint, so this only constrains
    # actual recurring series.
    op.create_unique_constraint(
        "uq_income_entries_series_id_expected_date",
        "income_entries", ["series_id", "expected_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_income_entries_series_id_expected_date", "income_entries", type_="unique")

    op.drop_constraint("uq_transactions_user_id_fingerprint", "transactions", type_="unique")
    op.create_unique_constraint("transactions_fingerprint_key", "transactions", ["fingerprint"])

    op.drop_constraint("uq_categories_user_id_name", "categories", type_="unique")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])

    for table in _TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"{table}_user_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "user_id")
