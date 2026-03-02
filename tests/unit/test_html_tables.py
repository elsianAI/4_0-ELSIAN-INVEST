"""Tests for table extraction ported from 3.0."""

from elsian.extract.html_tables import (
    parse_number,
    extract_from_markdown_table,
    extract_tables_from_clean_md,
    extract_tables_from_text,
    _identify_period_columns,
    _parse_markdown_table,
    _collapse_split_parentheticals,
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


# ── _collapse_split_parentheticals ──────────────────────────────────

def test_collapse_split_parens_basic():
    """Adjacent '( value' + ')' cells are collapsed into a single '(value)' cell."""
    cells = ["Cost of goods sold", "", "", "( 325.2", ")", "", "", "( 319.3", ")"]
    result = _collapse_split_parentheticals(cells)
    assert result == ["Cost of goods sold", "", "", "(325.2)", "", "", "(319.3)"]


def test_collapse_split_parens_multiple_pairs():
    """All four parenthetical pairs in an IOSP-style row are collapsed."""
    # Simulates: | CoGS |  |  | ( 325.2 | ) |  |  | ( 319.3 | ) |  |  | ( 957.4 | ) |  |  | ( 971.9 | ) |
    cells = [
        "CoGS", "", "",
        "( 325.2", ")", "", "",
        "( 319.3", ")", "", "",
        "( 957.4", ")", "", "",
        "( 971.9", ")",
    ]
    result = _collapse_split_parentheticals(cells)
    # 17 cells - 4 removed ')' = 13 cells
    assert len(result) == 13
    assert result[3] == "(325.2)"
    assert result[6] == "(319.3)"
    assert result[9] == "(957.4)"
    assert result[12] == "(971.9)"


def test_collapse_split_parens_no_collapse_when_already_closed():
    """Cells that already have closing paren are NOT collapsed."""
    cells = ["Item", "(500)", "(300)"]
    result = _collapse_split_parentheticals(cells)
    assert result == ["Item", "(500)", "(300)"]


def test_collapse_split_parens_lone_paren_not_collapsed():
    """A '(' cell with no adjacent ')' is left unchanged."""
    cells = ["Item", "( 100", "200"]  # next cell is not ')'
    result = _collapse_split_parentheticals(cells)
    assert result == ["Item", "( 100", "200"]


def test_split_paren_roundtrip_extraction():
    """End-to-end: split-cell parenthetical negatives extract as negative values."""
    # Mimics IOSP 10-Q IS table structure (2 periods for simplicity)
    table = (
        "| | 2025 | | 2024 |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| Net sales | $ | 441.9 | $ | 443.4 |\n"
        "| Cost of goods sold |  | ( 325.2 | ) | ( 319.3 | ) |\n"
        "| Gross profit |  | 116.7 |  | 124.1 |\n"
    )
    fields = extract_from_markdown_table(table)
    cogs_fields = [f for f in fields if "cost" in f.label.lower()]
    # Both periods should have extracted a negative COGS
    assert len(cogs_fields) >= 1
    for f in cogs_fields:
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
