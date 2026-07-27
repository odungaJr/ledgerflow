from decimal import Decimal

import pytest

from app.services.importer import (
    _make_fingerprint,
    _map_columns,
    _parse_date,
    _parse_pdf_row,
    _to_decimal,
    _PDF_LINE_RE,
    import_csv,
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


def test_parse_pdf_row_skips_header_row():
    assert _parse_pdf_row(["Date", "Description", "Debit", "Credit", "Balance"], ACCOUNT_ID) is None


def test_parse_pdf_row_parses_debit_row():
    row = _parse_pdf_row(["15/04/2024", "ATM WITHDRAWAL", "50000.00", "", "2340500.00"], ACCOUNT_ID)
    assert row is not None
    assert row["type"] == "debit"
    assert row["amount"] == Decimal("50000.00")


def test_parse_pdf_row_returns_none_when_no_amount():
    assert _parse_pdf_row(["15/04/2024", "NO AMOUNT ROW"], ACCOUNT_ID) is None
