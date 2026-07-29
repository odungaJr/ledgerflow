"""
Account Engine
==============
Computes an account's current balance from whichever data point is more
recent: the latest imported transaction's running balance, or a manually
entered "known balance as of X" (see Account.manual_balance). Neither
source is authoritative on its own — a manual entry naturally supersedes
older transaction history, and a newer transaction supersedes a stale
manual entry.
"""
from app.models.models import Account


def compute_balance(account: Account) -> dict:
    latest_txn = max(
        (t for t in account.transactions if t.balance_after is not None),
        key=lambda t: t.date,
        default=None,
    )

    candidates = []
    if latest_txn is not None:
        candidates.append((latest_txn.date, latest_txn.balance_after, "transaction"))
    if account.manual_balance is not None and account.manual_balance_date is not None:
        candidates.append((account.manual_balance_date, account.manual_balance, "manual"))

    if not candidates:
        return {"current_balance": None, "balance_as_of": None, "balance_source": None}

    as_of, balance, source = max(candidates, key=lambda c: c[0])
    return {"current_balance": float(balance), "balance_as_of": as_of, "balance_source": source}
