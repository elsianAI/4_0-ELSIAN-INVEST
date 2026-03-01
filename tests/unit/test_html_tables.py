"""Tests for table extraction ported from 3.0."""

from elsian.extract.html_tables import (
    parse_number,
    extract_from_markdown_table,
    extract_tables_from_clean_md,
    extract_tables_from_text,
    _identify_period_columns,
    _parse_markdown_table,
)


# ── parse_number ────────────────────────────────────────────────────

def test_parse_number_simple():
    assert parse_number("1,234") == 1234.0


def test_parse_number_negative_parens():
    assert parse_number("(1,234)") == -1234.0


def test_parse_number_negative_dash():
    assert parse_number("-500") == -500.0


def test_parse_number_dash_is_none():
    assert parse_number("\u2014") is None  # em dash
    assert parse_number("-") is None


def test_parse_number_european():
    assert parse_number("1.234,56") == 1234.56


def test_parse_number_currency_symbol():
    assert parse_number("$1,234") == 1234.0
    assert parse_number("\u20ac500") == 500.0


def test_parse_number_empty():
    assert parse_number("") is None
    assert parse_number("N/A") is None


# ── _identify_period_columns ────────────────────────────────────────

def test_period_columns_simple_years():
    headers = ["", "2024", "2023", "2022"]
    result = _identify_period_columns(headers)
    assert result == {1: "FY2024", 2: "FY2023", 3: "FY2022"}


def test_period_columns_year_ended():
    headers = ["", "Year Ended December 31, 2024", "Year Ended December 31, 2023"]
    result = _identify_period_columns(headers)
    assert result == {1: "FY2024", 2: "FY2023"}


def test_period_columns_three_months():
    headers = ["", "Three Months Ended September 30, 2024", "Three Months Ended September 30, 2023"]
    result = _identify_period_columns(headers)
    assert result == {1: "Q3-2024", 2: "Q3-2023"}


# ── extract_from_markdown_table ─────────────────────────────────────

def test_extract_simple_table():
    table = (
        "| | 2024 | 2023 |\n"
        "| --- | --- | --- |\n"
        "| Revenue | 83,902 | 84,477 |\n"
        "| Net income | 1,234 | 5,678 |\n"
    )
    fields = extract_from_markdown_table(table, "income_statement", table_idx=0)
    assert len(fields) == 4
    labels = {f.label for f in fields}
    assert "Revenue" in labels
    assert "Net income" in labels
    rev_2024 = [f for f in fields if f.label == "Revenue" and f.column_header == "FY2024"]
    assert len(rev_2024) == 1
    assert rev_2024[0].value == 83902.0


def test_extract_with_parenthetical_negatives():
    table = (
        "| | 2024 | 2023 |\n"
        "| --- | --- | --- |\n"
        "| Net loss | (500) | (300) |\n"
    )
    fields = extract_from_markdown_table(table)
    assert len(fields) == 2
    for f in fields:
        assert f.value < 0


def test_extract_percentage_table_skipped():
    table = (
        "| | 2024 | % | 2023 | % |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| Revenue | 100.0 | % | 100.0 | % |\n"
        "| Cost | 60.0 | % | 65.0 | % |\n"
    )
    fields = extract_from_markdown_table(table)
    assert len(fields) == 0


# ── extract_tables_from_clean_md ────────────────────────────────────

def test_extract_from_clean_md():
    md = (
        "## Income Statement\n"
        "\n"
        "| | 2024 | 2023 |\n"
        "| --- | --- | --- |\n"
        "| Revenue | 1,000 | 900 |\n"
        "| Net income | 200 | 150 |\n"
        "\n"
        "## Balance Sheet\n"
        "\n"
        "| | 2024 | 2023 |\n"
        "| --- | --- | --- |\n"
        "| Total assets | 5,000 | 4,800 |\n"
    )
    fields = extract_tables_from_clean_md(md, source_filename="test.md")
    assert len(fields) == 6
    assert any("income_statement" in f.source_location for f in fields)
    assert any("balance_sheet" in f.source_location for f in fields)


def test_source_location_includes_filename():
    md = (
        "| | 2024 |\n"
        "| --- | --- |\n"
        "| Revenue | 100 |\n"
    )
    fields = extract_tables_from_clean_md(md, source_filename="10k.md")
    assert all("10k.md" in f.source_location for f in fields)
