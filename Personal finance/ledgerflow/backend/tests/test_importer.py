from datetime import date
from decimal import Decimal

import pytest

from app.services.importer import (
    _make_fingerprint,
    _map_columns,
    _map_pdf_columns,
    _parse_date,
    _parse_pdf_row,
    _parse_pdf_words,
    _to_decimal,
    _PDF_LINE_RE,
    import_csv,
    import_pdf,
)

ACCOUNT_ID = "11111111-1111-1111-1111-111111111111"


# ── _to_decimal ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value, expected",
    [
        ("1,234.50", Decimal("1234.50")),
        (" 500.00 ", Decimal("500.00")),
        ("0", Decimal("0")),
        (100, Decimal("100")),
    ],
)
def test_to_decimal_valid(value, expected):
    assert _to_decimal(value) == expected


@pytest.mark.parametrize("value", ["", "abc", None, float("nan")])
def test_to_decimal_invalid_returns_none(value):
    assert _to_decimal(value) is None


# ── _parse_date ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value",
    ["15/04/2024", "2024-04-15", "15-04-2024", "15 Apr 2024", "15-Apr-2024"],
)
def test_parse_date_accepts_common_formats(value):
    parsed = _parse_date(value)
    assert parsed is not None
    assert parsed.year == 2024
    assert parsed.month == 4
    assert parsed.day == 15


def test_parse_date_invalid_returns_none():
    assert _parse_date("not-a-date") is None


# ── _make_fingerprint ────────────────────────────────────────────────────────

def test_fingerprint_is_deterministic():
    from datetime import date
    d = date(2024, 4, 15)
    fp1 = _make_fingerprint(ACCOUNT_ID, d, "ATM Withdrawal", Decimal("50000"))
    fp2 = _make_fingerprint(ACCOUNT_ID, d, "  ATM Withdrawal  ", Decimal("50000"))
    assert fp1 == fp2  # whitespace/case-insensitive on description


def test_fingerprint_differs_on_amount():
    from datetime import date
    d = date(2024, 4, 15)
    fp1 = _make_fingerprint(ACCOUNT_ID, d, "ATM Withdrawal", Decimal("50000"))
    fp2 = _make_fingerprint(ACCOUNT_ID, d, "ATM Withdrawal", Decimal("60000"))
    assert fp1 != fp2


# ── _map_columns ─────────────────────────────────────────────────────────────

def test_map_columns_recognises_aliases():
    fieldnames = ["Transaction Date", "Particulars", "Withdrawal", "Deposit", "Running Balance"]
    mapping = _map_columns(fieldnames)
    assert mapping["date"] == "Transaction Date"
    assert mapping["description"] == "Particulars"
    assert mapping["debit"] == "Withdrawal"
    assert mapping["credit"] == "Deposit"
    assert mapping["balance"] == "Running Balance"


# ── import_csv ───────────────────────────────────────────────────────────────

def test_import_csv_basic_debit_and_credit_rows():
    csv_bytes = (
        b"Date,Description,Debit,Credit,Balance\n"
        b"15/04/2024,ATM WITHDRAWAL KARIAKOO,50000.00,,2340500.00\n"
        b"16/04/2024,SALARY DEPOSIT,,1200000.00,3540500.00\n"
    )
    rows = import_csv(csv_bytes, ACCOUNT_ID)

    assert len(rows) == 2
    assert rows[0]["type"] == "debit"
    assert rows[0]["amount"] == Decimal("50000.00")
    assert rows[1]["type"] == "credit"
    assert rows[1]["amount"] == Decimal("1200000.00")
    assert rows[0]["fingerprint"] != rows[1]["fingerprint"]


def test_import_csv_skips_unparseable_and_empty_rows():
    csv_bytes = (
        b"Date,Description,Debit,Credit,Balance\n"
        b"not-a-date,SOME DESC,10.00,,100.00\n"
        b"15/04/2024,,10.00,,100.00\n"
        b"15/04/2024,ZERO VALUE ROW,,,100.00\n"
        b"16/04/2024,VALID ROW,20.00,,80.00\n"
    )
    rows = import_csv(csv_bytes, ACCOUNT_ID)
    assert len(rows) == 1
    assert rows[0]["description"] == "VALID ROW"


def test_import_csv_requires_date_and_description_columns():
    csv_bytes = b"Foo,Bar\n1,2\n"
    with pytest.raises(ValueError):
        import_csv(csv_bytes, ACCOUNT_ID)


# ── PDF line parsing (pure functions, no real PDF file needed) ───────────────

def test_pdf_line_regex_matches_typical_statement_line():
    line = "15/04/2024  ATM WITHDRAWAL KARIAKOO  50,000.00  -  2,340,500.00"
    m = _PDF_LINE_RE.search(line)
    assert m is not None
    raw_date, desc, debit, credit, balance = m.groups()
    assert raw_date == "15/04/2024"
    assert debit == "50,000.00"
    assert balance == "2,340,500.00"


STANDARD_COL_MAP = {"date": 0, "description": 1, "debit": 2, "credit": 3, "balance": 4}


def test_parse_pdf_row_skips_header_row():
    row = ["Date", "Description", "Debit", "Credit", "Balance"]
    assert _parse_pdf_row(row, STANDARD_COL_MAP, ACCOUNT_ID) is None


def test_parse_pdf_row_parses_debit_row():
    row = _parse_pdf_row(
        ["15/04/2024", "ATM WITHDRAWAL", "50000.00", "", "2340500.00"], STANDARD_COL_MAP, ACCOUNT_ID
    )
    assert row is not None
    assert row["type"] == "debit"
    assert row["amount"] == Decimal("50000.00")


def test_parse_pdf_row_returns_none_when_no_amount():
    col_map = {"date": 0, "description": 1}
    assert _parse_pdf_row(["15/04/2024", "NO AMOUNT ROW"], col_map, ACCOUNT_ID) is None


def test_parse_pdf_row_handles_non_standard_column_order():
    # Some banks list Deposit (credit) before Withdrawal (debit), plus extra columns.
    col_map = {"date": 1, "description": 2, "credit": 3, "debit": 4, "balance": 6}
    row = ["SN", "17/04/2026", "SALARY", "1500000.00", "", "extra", "3540500.00"]
    txn = _parse_pdf_row(row, col_map, ACCOUNT_ID)
    assert txn is not None
    assert txn["type"] == "credit"
    assert txn["amount"] == Decimal("1500000.00")
    assert txn["balance_after"] == Decimal("3540500.00")


# ── _map_pdf_columns ─────────────────────────────────────────────────────────

def test_map_pdf_columns_handles_multiline_headers_and_extra_columns():
    header = ["SN", "TRANS DATE", "DETAILS", "CHANNEL ID", "VALUE DATE", "DEBIT", "CREDIT", "BOOK BALANCE"]
    col_map = _map_pdf_columns(header)
    assert col_map["date"] == 1  # "trans date" preferred over "value date"
    assert col_map["description"] == 2
    assert col_map["debit"] == 5
    assert col_map["credit"] == 6
    assert col_map["balance"] == 7


def test_map_pdf_columns_deposit_before_withdrawal():
    header = ["Transaction\nDate", "Details", "Deposit", "Withdrawal", None, "Balance"]
    col_map = _map_pdf_columns(header)
    assert col_map["date"] == 0
    assert col_map["description"] == 1
    assert col_map["credit"] == 2  # Deposit
    assert col_map["debit"] == 3   # Withdrawal
    assert col_map["balance"] == 5


# ── _parse_date with embedded time ──────────────────────────────────────────

def test_parse_date_strips_embedded_time_component():
    parsed = _parse_date("2026-04-17\n23:10:53")
    assert parsed == date(2026, 4, 17)


# ── import_pdf error handling ────────────────────────────────────────────────

def test_import_pdf_returns_empty_list_on_unopenable_pdf(monkeypatch):
    def _raise(*args, **kwargs):
        raise TypeError("'PDFObjRef' object is not subscriptable")

    monkeypatch.setattr("app.services.importer.pdfplumber.open", _raise)
    assert import_pdf(b"not a real pdf", ACCOUNT_ID) == []


# ── _parse_pdf_words (word-position reconstruction) ─────────────────────────
# Mirrors the real layout of a bank statement whose line/table text extraction
# scrambles reading order (description wraps around the date, amounts land on
# a separate line from either) but whose word bounding boxes stay reliable.

class _FakePage:
    def __init__(self, words):
        self._words = words

    def extract_words(self):
        return self._words


def test_parse_pdf_words_reconstructs_a_scrambled_transaction():
    words = [
        {"text": "2026-04-13", "top": 203.6, "x0": 52.8, "x1": 93.2},
        {"text": "CRDBBANK", "top": 207.8, "x0": 110.5, "x1": 153.9},
        {"text": "Transfer", "top": 207.8, "x0": 156.4, "x1": 200.0},
        {"text": "500,000", "top": 208.2, "x0": 364.2, "x1": 393.0},
        {"text": "0", "top": 208.2, "x0": 457.3, "x1": 461.8},
        {"text": "500,596.87", "top": 208.2, "x0": 509.3, "x1": 549.0},
        {"text": "22:44:09", "top": 212.8, "x0": 57.4, "x1": 88.6},
    ]
    rows = _parse_pdf_words(_FakePage(words), ACCOUNT_ID)
    assert len(rows) == 1
    txn = rows[0]
    assert txn["date"] == date(2026, 4, 13)
    assert txn["type"] == "credit"
    assert txn["amount"] == Decimal("500000")
    assert txn["balance_after"] == Decimal("500596.87")
    assert "CRDBBANK" in txn["description"]
    assert "Transfer" in txn["description"]
    assert "22:44:09" not in txn["description"]  # time token excluded


def test_parse_pdf_words_splits_multiple_transactions_by_date_boundary():
    words = [
        {"text": "2026-04-13", "top": 100.0, "x0": 52.8, "x1": 93.2},
        {"text": "First", "top": 100.0, "x0": 110.5, "x1": 130.0},
        {"text": "40,000", "top": 100.0, "x0": 419.0, "x1": 450.0},
        {"text": "0", "top": 100.0, "x0": 364.0, "x1": 370.0},
        {"text": "460,596.87", "top": 100.0, "x0": 509.3, "x1": 549.0},
        {"text": "2026-04-14", "top": 120.0, "x0": 52.8, "x1": 93.2},
        {"text": "Second", "top": 120.0, "x0": 110.5, "x1": 135.0},
        {"text": "0", "top": 120.0, "x0": 419.0, "x1": 425.0},
        {"text": "300,000", "top": 120.0, "x0": 364.0, "x1": 393.0},
        {"text": "160,596.87", "top": 120.0, "x0": 509.3, "x1": 549.0},
    ]
    rows = _parse_pdf_words(_FakePage(words), ACCOUNT_ID)
    assert [r["date"] for r in rows] == [date(2026, 4, 13), date(2026, 4, 14)]
    assert rows[0]["type"] == "debit"
    assert rows[1]["type"] == "credit"


def test_parse_pdf_words_skips_rows_missing_all_three_amounts():
    words = [
        {"text": "2026-04-13", "top": 100.0, "x0": 52.8, "x1": 93.2},
        {"text": "Incomplete", "top": 100.0, "x0": 110.5, "x1": 140.0},
        {"text": "500,000", "top": 100.0, "x0": 364.0, "x1": 393.0},
        # missing withdrawal and balance tokens
    ]
    assert _parse_pdf_words(_FakePage(words), ACCOUNT_ID) == []
