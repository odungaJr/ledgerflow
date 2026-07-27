"""
Transaction Import Engine
=========================
Handles two input types:
  - CSV → stdlib csv parsing with header-name normalisation (banks vary in
    column order/naming, e.g. Debit/Withdrawal, Credit/Deposit).
  - PDF → three fallback tiers per page, since PDF layouts vary a lot more
    than CSVs and pdfplumber's grouping isn't always reliable:
      1. Table extraction, columns matched by name (same alias system as CSV).
      2. Word-position reconstruction — for PDFs with no reliable ruling
         lines, where pdfplumber's line/table text grouping scrambles
         reading order (a wrapped description can end up sandwiched around
         the date, with amounts on a different "line" than either). Word
         bounding boxes stay reliable even then.
      3. Single-line regex scan, for simple one-line-per-transaction layouts.
    A page falls through to the next tier only if the previous one produced
    zero actual transactions (not just a plausible-looking table header).

Both paths produce a list of RawTransaction dicts that the caller
persists and passes to the AI categoriser.

Usage:
    rows = import_csv(file_bytes, account_id)
    rows = import_pdf(file_bytes, account_id)
"""
import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TypedDict

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
    """Coerce a cell value to Decimal; return None on failure or blank/NaN cells."""
    try:
        cleaned = str(value).replace(",", "").replace(" ", "")
        if cleaned.lower() in ("", "nan", "none"):
            return None
        result = Decimal(cleaned)
        if result.is_nan():
            return None
        return result
    except (InvalidOperation, TypeError):
        return None


_DATE_FORMATS = [
    "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y",
    "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%Y/%m/%d", "%d %B %Y", "%d-%B-%Y",
]

# Strips a trailing time component (e.g. "2026-04-17 23:10:53" -> "2026-04-17"),
# which some PDF table exports combine with the date in a single multi-line cell.
_TRAILING_TIME_RE = re.compile(r"\s+\d{1,2}:\d{2}(:\d{2})?\s*$")


def _parse_date(value) -> date | None:
    """Try a few common East-African bank statement date formats (day-first)."""
    value_str = str(value or "").strip()
    # Collapse embedded newlines/extra whitespace from multi-line PDF table cells.
    value_str = " ".join(value_str.split())
    value_str = _TRAILING_TIME_RE.sub("", value_str).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue
    return None


# ── CSV importer ───────────────────────────────────────────────────────────────

# Normalise common column-name variations from different banks
_COL_ALIASES = {
    "date":        ["date", "transaction date", "trans date", "txn date", "value date"],
    "description": ["description", "particulars", "narration", "details", "memo"],
    "debit":       ["debit", "withdrawal", "dr", "debit amount"],
    "credit":      ["credit", "deposit", "cr", "credit amount"],
    "balance":     ["balance", "running balance", "closing balance", "book balance"],
}


def _map_columns(fieldnames: list[str]) -> dict[str, str]:
    """Return a mapping {canonical_name: actual_column_name} for recognised columns."""
    lower_cols = {c.lower().strip(): c for c in fieldnames}
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
    text = file_bytes.decode("utf-8-sig")  # utf-8-sig strips a BOM if present
    reader = csv.DictReader(io.StringIO(text))
    col = _map_columns(reader.fieldnames or [])

    if "date" not in col or "description" not in col:
        raise ValueError("CSV must have at least Date and Description columns.")

    rows: list[RawTransaction] = []

    for row in reader:
        txn_date = _parse_date(row.get(col["date"]))
        if txn_date is None:
            continue  # skip unparseable rows (headers embedded in body, etc.)

        description = str(row.get(col["description"]) or "").strip()
        if not description or description.lower() in ("nan", "none", ""):
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


def _normalise_header_cell(value) -> str:
    """Collapse embedded whitespace/newlines in a PDF table header cell for alias matching."""
    return " ".join(str(value or "").split()).lower()


def _map_pdf_columns(header_row: list) -> dict[str, int]:
    """
    Return a mapping {canonical_name: column_index} for a PDF table's header row.
    Column order and count vary by bank (e.g. some list Deposit before Withdrawal,
    others add SN/Channel ID/Value Date columns) — this reads names, not positions.
    """
    lower_cols = {_normalise_header_cell(cell): idx for idx, cell in enumerate(header_row)}
    mapping = {}
    for canonical, aliases in _COL_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                mapping[canonical] = lower_cols[alias]
                break
    return mapping


# Some banks' PDFs have no reliable ruling lines, so pdfplumber's table/line-text
# extraction scrambles reading order (a wrapped description can end up sandwiched
# around the date, with amounts appearing on a different line than either). Word
# bounding boxes are still reliable even then, so this reconstructs each
# transaction from x-position (column) rather than from line grouping.
_DATE_TOKEN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_TOKEN_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
_MONEY_TOKEN_RE = re.compile(r"^[\d,]+(\.\d{2})?$")
_AMOUNT_COLUMN_X0 = 340  # left edge below which text is treated as description, not an amount


def _parse_pdf_words(page, account_id: str) -> list[RawTransaction]:
    """
    Reconstruct transactions from a page's word bounding boxes. Groups words
    into one row per date-token occurrence (from that date's vertical position
    up to the next one), then classifies each row's words by x-position: the
    three rightmost money-shaped tokens are deposit, withdrawal, and balance
    (in that left-to-right column order), and everything else left of them is
    description text.
    """
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    date_words = [w for w in words if _DATE_TOKEN_RE.match(w["text"])]
    if not date_words:
        return []

    rows: list[RawTransaction] = []
    for i, date_word in enumerate(date_words):
        band_start = date_word["top"] - 2
        band_end = date_words[i + 1]["top"] - 2 if i + 1 < len(date_words) else float("inf")
        band_words = [w for w in words if band_start <= w["top"] < band_end]

        money_tokens = sorted(
            (w for w in band_words if w["x0"] > _AMOUNT_COLUMN_X0 and _MONEY_TOKEN_RE.match(w["text"])),
            key=lambda w: w["x0"],
        )[-3:]
        if len(money_tokens) < 3:
            continue  # can't reliably identify deposit/withdrawal/balance
        deposit_tok, withdrawal_tok, balance_tok = money_tokens

        excluded_ids = {id(date_word), id(deposit_tok), id(withdrawal_tok), id(balance_tok)}
        description = " ".join(
            w["text"] for w in band_words
            if id(w) not in excluded_ids
            and w["x0"] <= _AMOUNT_COLUMN_X0
            and not _TIME_TOKEN_RE.match(w["text"])
        ).strip()
        if not description:
            continue

        txn_date = _parse_date(date_word["text"])
        if txn_date is None:
            continue

        debit  = _to_decimal(withdrawal_tok["text"]) or Decimal(0)
        credit = _to_decimal(deposit_tok["text"])    or Decimal(0)
        balance = _to_decimal(balance_tok["text"])

        if debit > 0:
            amount, txn_type = debit, "debit"
        elif credit > 0:
            amount, txn_type = credit, "credit"
        else:
            continue

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


def import_pdf(file_bytes: bytes, account_id: str) -> list[RawTransaction]:
    """
    Extract transactions from a PDF bank statement using pdfplumber.
    Falls back to a best-effort regex scan of each page's text.
    """
    rows: list[RawTransaction] = []

    try:
        pdf_context = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception:
        # Some PDFs have malformed encryption metadata that pdfminer can't parse
        # (e.g. an indirect reference where it expects a literal name) — nothing
        # we can recover from, so report zero transactions rather than crashing.
        return rows

    with pdf_context as pdf:
        for page in pdf.pages:
            # First attempt: use pdfplumber's table extraction (works on structured PDFs).
            # A single malformed table/page shouldn't fail the whole import.
            try:
                tables = page.extract_tables()
            except Exception:
                tables = []

            table_rows_found = 0
            for table in tables:
                if not table:
                    continue
                header, *data_rows = table
                col_map = _map_pdf_columns(header)
                if "date" not in col_map or "description" not in col_map:
                    continue  # not a transactions table (e.g. an account-info table)
                for line in data_rows:
                    if line is None:
                        continue
                    txn = _parse_pdf_row(line, col_map, account_id)
                    if txn:
                        rows.append(txn)
                        table_rows_found += 1

            # A header can match while every data row is misaligned/empty (some
            # banks' PDFs have no reliable ruling lines) — only trust the table
            # if it actually produced rows, otherwise fall through to the more
            # tolerant word-position/text parsers below for this same page.
            if table_rows_found > 0:
                continue

            # Second attempt: reconstruct rows from word positions (handles PDFs
            # where the table/line grouping scrambles reading order).
            try:
                word_rows = _parse_pdf_words(page, account_id)
            except Exception:
                word_rows = []
            if word_rows:
                rows.extend(word_rows)
                continue

            # Third attempt: raw text scan, for pages with no recognisable table
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


def _parse_pdf_row(cells: list, col_map: dict[str, int], account_id: str) -> RawTransaction | None:
    """Parse a single table row extracted by pdfplumber, using its header-derived column map."""
    def cell(name: str):
        idx = col_map.get(name)
        if idx is None or idx >= len(cells):
            return None
        return cells[idx]

    txn_date = _parse_date(cell("date"))
    if txn_date is None:
        # Also catches stray repeated header rows — their "date" cell won't parse.
        return None

    description = str(cell("description") or "").strip()
    if not description:
        return None

    debit  = _to_decimal(cell("debit"))  or Decimal(0)
    credit = _to_decimal(cell("credit")) or Decimal(0)
    balance = _to_decimal(cell("balance"))

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
        balance_after= balance,
        fingerprint  = fingerprint,
    )
