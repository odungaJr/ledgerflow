"""
Transaction Import Engine
=========================
Handles two input types:
  - CSV  → pandas-based parsing with column-name normalisation
  - PDF  → pdfplumber text extraction, line-by-line regex parsing

Both paths produce a list of RawTransaction dicts that the caller
persists and passes to the AI categoriser.

Usage:
    rows = import_csv(file_bytes, account_id)
    rows = import_pdf(file_bytes, account_id)
"""
import hashlib
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TypedDict

import pandas as pd
import pdfplumber


# ── Shared types ───────────────────────────────────────────────────────────────

class RawTransaction(TypedDict):
    account_id  : str
    date        : date
    description : str
    amount      : Decimal
    type        : str        # "debit" | "credit"
    balance_after: Decimal | None
    fingerprint : str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_fingerprint(account_id: str, txn_date: date, description: str, amount: Decimal) -> str:
    """SHA-256 hash used to detect duplicate imports across batches."""
    raw = f"{account_id}|{txn_date}|{description.strip().lower()}|{amount}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _to_decimal(value) -> Decimal | None:
    """Coerce a cell value to Decimal; return None on failure."""
    try:
        cleaned = str(value).replace(",", "").replace(" ", "")
        return Decimal(cleaned)
    except (InvalidOperation, TypeError):
        return None


def _parse_date(value) -> date | None:
    """Try a few common East-African bank statement date formats."""
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y"]
    value_str = str(value).strip()
    for fmt in formats:
        try:
            return date.fromisoformat(pd.to_datetime(value_str, format=fmt).date().isoformat())
        except Exception:
            continue
    try:
        return pd.to_datetime(value_str, dayfirst=True).date()
    except Exception:
        return None


# ── CSV importer ───────────────────────────────────────────────────────────────

# Normalise common column-name variations from different banks
_COL_ALIASES = {
    "date":        ["date", "transaction date", "txn date", "value date"],
    "description": ["description", "particulars", "narration", "details", "memo"],
    "debit":       ["debit", "withdrawal", "dr", "debit amount"],
    "credit":      ["credit", "deposit", "cr", "credit amount"],
    "balance":     ["balance", "running balance", "closing balance"],
}


def _map_columns(df: pd.DataFrame) -> dict[str, str]:
    """Return a mapping {canonical_name: actual_df_column} for recognised columns."""
    lower_cols = {c.lower().strip(): c for c in df.columns}
    mapping = {}
    for canonical, aliases in _COL_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                mapping[canonical] = lower_cols[alias]
                break
    return mapping


def import_csv(file_bytes: bytes, account_id: str) -> list[RawTransaction]:
    """
    Parse a CSV bank statement.
    Supports separate Debit/Credit columns or a single signed Amount column.
    """
    df = pd.read_csv(io.BytesIO(file_bytes))
    col = _map_columns(df)

    if "date" not in col or "description" not in col:
        raise ValueError("CSV must have at least Date and Description columns.")

    rows: list[RawTransaction] = []

    for _, row in df.iterrows():
        txn_date = _parse_date(row[col["date"]])
        if txn_date is None:
            continue  # skip unparseable rows (headers embedded in body, etc.)

        description = str(row[col["description"]]).strip()
        if not description or description.lower() in ("nan", ""):
            continue

        debit  = _to_decimal(row.get(col.get("debit",  ""), "")) or Decimal(0)
        credit = _to_decimal(row.get(col.get("credit", ""), "")) or Decimal(0)
        balance = _to_decimal(row.get(col.get("balance", ""), ""))

        # Determine amount and direction
        if debit > 0:
            amount, txn_type = debit, "debit"
        elif credit > 0:
            amount, txn_type = credit, "credit"
        else:
            continue  # zero-value row — skip

        fingerprint = _make_fingerprint(account_id, txn_date, description, amount)

        rows.append(RawTransaction(
            account_id   = account_id,
            date         = txn_date,
            description  = description,
            amount       = amount,
            type         = txn_type,
            balance_after= balance,
            fingerprint  = fingerprint,
        ))

    return rows


# ── PDF importer ───────────────────────────────────────────────────────────────

# Regex for a typical bank-statement line:
# "15/04/2024  ATM WITHDRAWAL KARIAKOO  50,000.00  -  2,340,500.00"
# Groups: date | description | debit | credit | balance
_PDF_LINE_RE = re.compile(
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"      # date
    r"\s+(.+?)\s+"                            # description (non-greedy)
    r"([\d,]+\.\d{2})?"                       # debit (optional)
    r"\s*[-–]?\s*"
    r"([\d,]+\.\d{2})?"                       # credit (optional)
    r"\s+([\d,]+\.\d{2})"                     # closing balance (required)
)


def import_pdf(file_bytes: bytes, account_id: str) -> list[RawTransaction]:
    """
    Extract transactions from a PDF bank statement using pdfplumber.
    Falls back to a best-effort regex scan of each page's text.
    """
    rows: list[RawTransaction] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            # First attempt: use pdfplumber's table extraction (works on structured PDFs)
            tables = page.extract_tables()
            for table in tables:
                for line in table:
                    if line is None or len(line) < 3:
                        continue
                    txn = _parse_pdf_row(line, account_id)
                    if txn:
                        rows.append(txn)

            # Second attempt: raw text scan for PDFs without embedded tables
            if not tables:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    m = _PDF_LINE_RE.search(line)
                    if not m:
                        continue
                    raw_date, desc, debit_str, credit_str, balance_str = m.groups()
                    txn_date = _parse_date(raw_date)
                    if txn_date is None:
                        continue

                    debit   = _to_decimal(debit_str)  or Decimal(0)
                    credit  = _to_decimal(credit_str) or Decimal(0)
                    balance = _to_decimal(balance_str)

                    if debit > 0:
                        amount, txn_type = debit, "debit"
                    elif credit > 0:
                        amount, txn_type = credit, "credit"
                    else:
                        continue

                    fingerprint = _make_fingerprint(account_id, txn_date, desc.strip(), amount)
                    rows.append(RawTransaction(
                        account_id   = account_id,
                        date         = txn_date,
                        description  = desc.strip(),
                        amount       = amount,
                        type         = txn_type,
                        balance_after= balance,
                        fingerprint  = fingerprint,
                    ))

    return rows


def _parse_pdf_row(cells: list, account_id: str) -> RawTransaction | None:
    """Parse a single table row extracted by pdfplumber."""
    # Skip header rows
    if any(h in str(cells[0]).lower() for h in ("date", "trans", "descr")):
        return None

    txn_date = _parse_date(cells[0])
    if txn_date is None:
        return None

    description = str(cells[1]).strip() if len(cells) > 1 else ""
    if not description:
        return None

    # Columns 2+ may be: debit, credit, balance or amount, type, balance
    debit  = _to_decimal(cells[2]) if len(cells) > 2 else Decimal(0)
    credit = _to_decimal(cells[3]) if len(cells) > 3 else Decimal(0)
    bal    = _to_decimal(cells[4]) if len(cells) > 4 else None

    debit  = debit  or Decimal(0)
    credit = credit or Decimal(0)

    if debit > 0:
        amount, txn_type = debit, "debit"
    elif credit > 0:
        amount, txn_type = credit, "credit"
    else:
        return None

    fingerprint = _make_fingerprint(account_id, txn_date, description, amount)
    return RawTransaction(
        account_id   = account_id,
        date         = txn_date,
        description  = description,
        amount       = amount,
        type         = txn_type,
        balance_after= bal,
        fingerprint  = fingerprint,
    )
