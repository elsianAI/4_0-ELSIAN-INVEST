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


# ── Bug A: $ currency-prefix colspan headers (grouped year assignment) ───────

def test_grouped_subheader_two_periods_same_type():
    """Bug A (simple): single 'Three Months Ended' with 2023+2024 sub-years.

    GCT Q1-type table: the HTML colspan creates an empty header at col 3,
    so the na\u00efve merge produced 'FY2024' instead of 'Q1-2024'.
    After the grouped-year fix, col 3 inherits the 'Three Months Ended'
    context from col 1 and is correctly labelled Q1-2024.
    """
    table = (
        "|  | Three Months Ended March 31, |  |  |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "|  | 2023 |  | 2024 |  |  |  |  |\n"
        "| Service revenues | $ | 35,096 |  |  | $ | 67,415 |  |\n"
        "| Total revenues | 127,797 |  |  | 251,077 |  |  |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-Q")
    by_period = {
        (f.label, f.column_header): f.value
        for f in fields
        if f.label in {"Service revenues", "Total revenues"}
    }
    # Total revenues — no $ prefix, values via sparse scan
    assert by_period.get(("Total revenues", "Q1-2023")) == 127797.0
    assert by_period.get(("Total revenues", "Q1-2024")) == 251077.0
    # Service revenues — $ prefix, values via dollar calibration
    assert by_period.get(("Service revenues", "Q1-2023")) == 35096.0
    assert by_period.get(("Service revenues", "Q1-2024")) == 67415.0
    # Must NOT produce wrong FY labels
    assert ("Total revenues", "FY2024") not in by_period
    assert ("Service revenues", "FY2024") not in by_period


def test_grouped_subheader_four_periods_two_types():
    """Bug A (complex): 'Three Months' + 'Nine Months' with 4 sub-years.

    GCT Q3-type table: 2 colspan headers \u00d7 2 years each.
    The na\u00efve merge assigned year 2024 (at col 3) to 'Nine Months', but
    it belongs to 'Three Months'.  The grouped-year fix distributes the
    4 years evenly: 2 per group.

    Non-$ rows rely on numeric anchor calibration (needs >= 3 matching rows).
    $ rows use dollar calibration directly regardless of row count.
    """
    table = (
        "|  | Three Months Ended Sep 30, |  | Nine Months Ended Sep 30, "
        "|  |  |  |  |  |  |  |  |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- "
        "| --- | --- | --- | --- | --- | --- |\n"
        "|  | 2023 |  | 2024 |  | 2023 |  | 2024 |  |  |  |  |  |  |  |  |\n"
        "| Total revenues | 178,167 |  |  | 303,316 |  |  | 459,094 |  |  | 865,260 |  |  |  |  |  |\n"
        "| Gross profit | 48,858 |  |  | 77,251 |  |  | 118,796 |  |  | 220,246 |  |  |  |  |  |\n"
        "| Operating income | 31,699 |  |  | 55,000 |  |  | 90,000 |  |  | 175,000 |  |  |  |  |  |\n"
        "| Service revenues | $ | 51,474 |  |  | $ | 100,373 |  |  | $ | 129,848 |  |  | $ | 253,166 |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-Q")
    by_period = {
        (f.label, f.column_header): f.value
        for f in fields
        if f.label in {"Total revenues", "Service revenues", "Gross profit"}
    }
    # Total revenues (no $ prefix \u2014 relies on numeric anchor calibration)
    assert by_period.get(("Total revenues", "Q3-2023")) == 178167.0
    assert by_period.get(("Total revenues", "Q3-2024")) == 303316.0
    assert by_period.get(("Total revenues", "9M-2023")) == 459094.0
    assert by_period.get(("Total revenues", "9M-2024")) == 865260.0
    # Service revenues ($ prefix \u2014 uses dollar calibration)
    assert by_period.get(("Service revenues", "Q3-2023")) == 51474.0
    assert by_period.get(("Service revenues", "Q3-2024")) == 100373.0
    assert by_period.get(("Service revenues", "9M-2023")) == 129848.0
    assert by_period.get(("Service revenues", "9M-2024")) == 253166.0
    # Must NOT produce wrong FY / 9M-as-FY labels
    for bad in ("FY2023", "FY2024"):
        assert ("Total revenues", bad) not in by_period


# ── Bug B: scale-note first cell in subheader row ────────────────────────────

def test_scale_note_first_cell_detected_as_subheader():
    """Bug B: rows with '(in millions, ...)' in the first cell must still be
    recognised as subheaders when the remaining cells contain years.

    Before the fix, _is_subheader_row() returned False, the year row was
    treated as data, no periods were found, and extraction produced nothing
    (or filed values under 'unknown').
    """
    table = (
        "|  |  | Three Months Ended Jun 30, |  |  | Six Months Ended Jun 30, "
        "|  |  |  |  |  |  |  |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- "
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| (in millions, except share and per share data) |  | 2025 |  |  | 2024 |  |  | 2025 |  |  | 2024 |  |  |  |  |  |\n"
        "| Net sales |  | $ | 439.7 |  |  | $ | 435.0 |  |  | $ | 880.5 |  |  | $ | 935.2 |  |\n"
        "| Gross profit |  |  | 123.2 |  |  |  | 126.9 |  |  |  | 248.3 |  |  |  | 282.6 |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-Q")
    by_period = {
        (f.label, f.column_header): f.value
        for f in fields
        if f.label in {"Net sales", "Gross profit"}
    }
    # Net sales — 4 period/year combinations
    assert by_period.get(("Net sales", "Q2-2025")) == 439.7
    assert by_period.get(("Net sales", "Q2-2024")) == 435.0
    assert by_period.get(("Net sales", "H1-2025")) == 880.5
    assert by_period.get(("Net sales", "H1-2024")) == 935.2
    # Gross profit (no $ prefix)
    assert by_period.get(("Gross profit", "Q2-2025")) == 123.2
    assert by_period.get(("Gross profit", "Q2-2024")) == 126.9
    # Must NOT produce 'unknown' period
    assert all(f.column_header != "unknown" for f in fields if f.label in {"Net sales", "Gross profit"})


# ── Bug GCT-Q1-2024: dollar/pct annotation-row filter ────────────────────────

def test_dollar_pct_annotation_row_skips_table():
    """MD&A comparison tables with a '$ / %' annotation row are skipped.

    GCT 2024 10-Qs contain tables like:
        |  | 2023  |  | 2024  |           ← year sub-header (consumed)
        |  | $  |  | %  |  | $  |  | %  |  ← annotation row
        | Total revenues | 127,797 | | | 100.0 | | | 251,077 | | | 100.0 | |

    The year sub-header places Q1-2024 at col 3, but the actual 2024
    dollar values sit at col 7.  The sparse scan from col 3 picks up
    100.0 (pct) instead of 251,077 (dollar).

    The fix: detect the annotation row and return [] immediately.
    """
    table = (
        "|  | Three Months Ended March 31, |  |  |  |  |  |  |  |  |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "|  | 2023 |  | 2024 |  |  |  |  |  |  |  |  |  |  |\n"
        "|  | $ |  | % |  | $ |  | % |  |  |  |  |  |  |\n"
        "|  | (In thousands, except for percentages) |  |  |  |  |  |  |  |  |  |  |  |  |\n"
        "| Revenues |  |  |  |  |  |  |  |  |  |  |  |  |  |\n"
        "| Service revenues | $ | 35,096 |  |  | 27.5 |  |  | $ | 67,415 |  |  | 26.9 |  |\n"
        "| Product revenues | 92,701 |  |  | 72.5 |  |  | 183,662 |  |  | 73.1 |  |  |  |\n"
        "| Total revenues | 127,797 |  |  | 100.0 |  |  | 251,077 |  |  | 100.0 |  |  |  |\n"
        "| Operating income | 17,856 |  |  | 14.0 |  |  | 34,817 |  |  | 13.9 |  |  |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-Q")
    # The whole table must be skipped — no extraction from the pct/dollar mix
    assert fields == []


def test_dollar_pct_annotation_row_does_not_suppress_normal_is_table():
    """The IS table with $ markers but NO annotation row must extract correctly.

    The plain IS table (no '| | $ | | % |' annotation row) should still
    extract dollar values from rows with and without $ prefixes.
    """
    table = (
        "|  | Three Months Ended March 31, |  |  |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "|  | 2023 |  | 2024 |  |  |  |  |\n"
        "| Revenues |  |  |  |  |  |  |  |\n"
        "| Service revenues | $ | 35,096 |  |  | $ | 67,415 |  |\n"
        "| Product revenues | 92,701 |  |  | 183,662 |  |  |  |\n"
        "| Total revenues | 127,797 |  |  | 251,077 |  |  |  |\n"
        "| Operating income | 17,856 |  |  | 34,817 |  |  |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-Q")
    by_period = {(f.label, f.column_header): f.value for f in fields}
    # Dollar values must be extracted correctly from both $ and non-$ rows
    assert by_period.get(("Total revenues", "Q1-2024")) == 251077.0
    assert by_period.get(("Total revenues", "Q1-2023")) == 127797.0
    assert by_period.get(("Service revenues", "Q1-2024")) == 67415.0
    assert by_period.get(("Service revenues", "Q1-2023")) == 35096.0
    assert by_period.get(("Operating income", "Q1-2024")) == 34817.0


# ── NEXN 6-K: 4-column table with reversed group order (9M then Q) ───────────

def test_nexn_6k_nine_months_then_three_months_column_order():
    """6-K sub-table where cumulative (9M) columns come BEFORE quarterly (Q3).

    NEXN (and similar foreign private issuers) file 6-K interim reports
    that include a combined IFRS statement table with the column order:
    9M-current | 9M-prior | Q3-current | Q3-prior

    The HTML-to-markdown conversion places the period-type header at the
    FIRST data column of each group (positions 2 and 5), but the actual
    values land at positions 3, 7, 11, 15 (offset +1 per column, +4 at
    the last column).  This produces max_drift=4, which previously exceeded
    the threshold of 3, causing the calibration to be rejected and Q3-2024
    to receive the Q3-2025 value instead of the correct prior-year value.

    After the fix (_max_drift <= 4), recalibration succeeds and each column
    receives its correct year value.
    """
    # Replicates the NEXN SRC_010 / SRC_011 sub-table format (IFRS statements).
    # Header: "9M ended Sep 30" at col 2, "Q3 ended Sep 30" at col 5.
    # Sub-years 2025,2024 at cols 2,5 and 2025,2024 at cols 11,14.
    table = (
        "|  |  | For the nine months ended September 30 |  |"
        "  | For the three months ended September 30 |  |  |  |  |  |  |  |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---"
        " | --- | --- | --- | --- | --- | --- | --- |\n"
        "|  |  | 2025 |  |  | 2024 |  |  | 2025 |  |  | 2024 |  |  |  |  |  |\n"
        "| Revenue |  |  | 264,069 |  |  |  | 253,193 |  |  |  | 94,791 |  |  |  | 90,184 |  |\n"
        "| Cost of revenue |  |  | 39,518 |  |  |  | 43,952 |  |  |  | 16,262 |  |  |  | 13,857 |  |\n"
        "| Gross profit |  |  | 186,782 |  |  |  | 174,008 |  |  |  | 65,585 |  |  |  | 64,309 |  |\n"
        "| Operating income |  |  | 19,918 |  |  |  | 16,342 |  |  |  | 7,273 |  |  |  | 16,303 |  |\n"
        "| Net income |  |  | 14,507 |  |  |  | 10,583 |  |  |  | 4,208 |  |  |  | 14,541 |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="6-K")
    by_period = {(f.label, f.column_header): f.value for f in fields}

    # 9M values must be correct
    assert by_period.get(("Revenue", "9M-2025")) == 264069.0
    assert by_period.get(("Revenue", "9M-2024")) == 253193.0
    # Q3 values must use the CORRECT prior-year column (Q3-2024 = 90,184, NOT 94,791)
    assert by_period.get(("Revenue", "Q3-2025")) == 94791.0
    assert by_period.get(("Revenue", "Q3-2024")) == 90184.0, (
        f"Q3-2024 Revenue should be 90184 (prior year), got {by_period.get(('Revenue','Q3-2024'))}"
    )
    # Cross-check other fields to ensure consistent recalibration
    assert by_period.get(("Net income", "Q3-2025")) == 4208.0
    assert by_period.get(("Net income", "Q3-2024")) == 14541.0


def test_nexn_6k_six_months_then_three_months_column_order():
    """6-K sub-table for H1 reports: H1 columns before Q2 columns.

    Same pattern as the 9M test but for semi-annual (H1 = six months)
    combined with Q2 (three months ended June 30).
    """
    table = (
        "|  |  | For the six months ended June 30 |  |"
        "  | For the three months ended June 30 |  |  |  |  |  |  |  |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---"
        " | --- | --- | --- | --- | --- | --- | --- |\n"
        "|  |  | 2025 |  |  | 2024 |  |  | 2025 |  |  | 2024 |  |  |  |  |  |\n"
        "| Revenue |  |  | 169,278 |  |  |  | 163,009 |  |  |  | 90,948 |  |  |  | 88,577 |  |\n"
        "| Cost of revenue |  |  | 23,256 |  |  |  | 30,095 |  |  |  | 12,057 |  |  |  | 15,557 |  |\n"
        "| Gross profit |  |  | 120,197 |  |  |  | 107,699 |  |  |  | 66,634 |  |  |  | 51,425 |  |\n"
        "| Operating income |  |  | 12,470 |  |  |  | 9,069 |  |  |  | 8,704 |  |  |  | 4,469 |  |\n"
        "| Net income |  |  | 10,299 |  |  |  | 42 |  |  |  | 8,666 |  |  |  | 725 |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="6-K")
    by_period = {(f.label, f.column_header): f.value for f in fields}

    # H1 values
    assert by_period.get(("Revenue", "H1-2025")) == 169278.0
    assert by_period.get(("Revenue", "H1-2024")) == 163009.0
    # Q2 values — Q2-2024 must be 88,577, NOT 90,948 (Q2-2025)
    assert by_period.get(("Revenue", "Q2-2025")) == 90948.0
    assert by_period.get(("Revenue", "Q2-2024")) == 88577.0, (
        f"Q2-2024 Revenue should be 88577 (prior year), got {by_period.get(('Revenue','Q2-2024'))}"
    )


# ── BL-039: ZWS stripping, "Twelve Months Ended", pro-forma guard ──


def test_strip_invisible_zero_width_space():
    """_strip_invisible removes U+200B zero-width spaces (BL-039 Fix 1)."""
    from elsian.extract.html_tables import _strip_invisible

    assert _strip_invisible("\u200b") == ""
    assert _strip_invisible("\u200bFoo\u200b") == "Foo"
    assert _strip_invisible("Clean") == "Clean"
    assert _strip_invisible("  \u200b  ") == ""  # strips whitespace too


def test_twelve_months_ended_period_detection():
    """'Twelve months ended' is recognised as a period indicator (BL-039 Fix 2)."""
    table = (
        "|  | Twelve months ended |  |\n"
        "| --- | --- | --- |\n"
        "|  | December 31, 2024 | December 31, 2023 |\n"
        "| Revenue | 100,000 | 90,000 |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-K")
    by_period = {(f.label, f.column_header): f.value for f in fields}
    assert by_period.get(("Revenue", "FY2024")) == 100000.0
    assert by_period.get(("Revenue", "FY2023")) == 90000.0


def test_year_ended_period_detection():
    """'Year ended' (without 'Twelve months') is recognised (BL-039 Fix 2)."""
    table = (
        "|  | Year ended |  |\n"
        "| --- | --- | --- |\n"
        "|  | December 31, 2024 | December 31, 2023 |\n"
        "| Revenue | 200,000 | 180,000 |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-K")
    by_period = {(f.label, f.column_header): f.value for f in fields}
    assert by_period.get(("Revenue", "FY2024")) == 200000.0
    assert by_period.get(("Revenue", "FY2023")) == 180000.0


def test_pro_forma_column_skipped():
    """Pro-forma columns are excluded from period identification (BL-039 Fix 4).

    NVDA has note tables headed 'Pro Forma / Year Ended / January 31, 2021'
    that contain hypothetical values; these must not produce period mappings.
    """
    table = (
        "|  | Pro Forma |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "|  | Year Ended |  |  |  |  |\n"
        "|  | January 31, 2021 |  |  |  |  |\n"
        "|  | (In millions) |  |  |  |  |\n"
        "| Revenue | $ | 17,104 |  |  |  |\n"
        "| Net income | $ | 4,757 |  |  |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-K")
    # Pro forma table should produce no period-mapped fields because
    # the merged header "Pro Forma Year Ended January 31, 2021" is
    # filtered out by the pro-forma guard.
    period_mapped = [f for f in fields if f.column_header.startswith("FY")]
    assert period_mapped == [], (
        f"Pro-forma table should not produce FY-mapped fields, got: "
        f"{[(f.label, f.column_header, f.value) for f in period_mapped]}"
    )


def test_zws_subheader_detection():
    """ZWS characters in table cells don't block sub-header detection (BL-039 Fix 1).

    ACLS clean.md files have U+200B in otherwise-empty first cells of sub-header
    rows, causing _is_subheader_row to return False if not stripped.
    """
    table = (
        "| \u200b | \u200b | Twelve months ended |  |  |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| \u200b | \u200b | December 31, 2024 | December 31, 2023 |  |\n"
        "| Revenue | \u200b | 100,000 | 90,000 |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-K")
    by_period = {(f.label, f.column_header): f.value for f in fields}
    assert by_period.get(("Revenue", "FY2024")) == 100000.0, (
        f"ZWS in cells should not block period detection. Got periods: "
        f"{set(f.column_header for f in fields)}"
    )


def test_orphaned_date_fragment_merged():
    """Orphaned date fragments are merged with period-type-only headers (BL-039 Fix 6).

    Grouped-year sub-header consumption can produce headers like
    "Three months ended 2022" (period-type + year, no month) when the
    month part ("June 30,") sits in an adjacent column.  The post-processing
    step should merge the fragment into the header so period detection works.
    """
    table = (
        "|  |  | Three months ended |  |  |  |  |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "|  |  | June 30, |  | June 30, |  |  |\n"
        "|  |  | 2022 |  | 2021 |  |  |\n"
        "| Revenue | $ | 180,453 |  | $ | 156,792 |  |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="10-Q")
    by_period = {(f.label, f.column_header): f.value for f in fields}
    assert by_period.get(("Revenue", "Q2-2022")) == 180453.0, (
        f"Orphaned date fragment should be merged. Got: "
        f"{[(f.label, f.column_header, f.value) for f in fields]}"
    )
    assert by_period.get(("Revenue", "Q2-2021")) == 156792.0


def test_income_from_operations_section_primary():
    """Sections named 'Income from operations' get PRIMARY bonus, not deprioritized (BL-039 Fix 7).

    The regex ':income.*from_operations' in DEPRIORITIZED incorrectly matched
    ':income_from_operations' (the actual IS section).  Adding it to PRIMARY
    ensures it's checked first and gets bonus=5.
    """
    from elsian.extract.phase import _section_bonus
    # income_from_operations is the main IS section in ACLS filings
    bonus = _section_bonus("income_statement:income_from_operations:tbl1:row5:col2")
    assert bonus == 5, f"income_from_operations should get PRIMARY bonus=5, got {bonus}"

    # income_loss_from_operations should still be deprioritized
    penalty = _section_bonus("income_statement:income_loss_from_operations:tbl2:row3:col1")
    assert penalty == -5, f"income_loss_from_operations should get DEPRIORITIZED penalty=-5, got {penalty}"


def test_income_tax_provision_label_priority():
    """'Income tax provision' gets high label priority for income_tax field (BL-039 Fix 7).

    This ensures the IS 'Income tax provision' row wins over CF 'Income taxes'
    in per-filing collision resolution even without section_bonus differences.
    """
    from elsian.normalize.aliases import AliasResolver
    lp_provision = AliasResolver.label_priority("income_tax", "Income tax provision")
    lp_taxes = AliasResolver.label_priority("income_tax", "Income taxes")
    assert lp_provision > lp_taxes, (
        f"'Income tax provision' priority ({lp_provision}) should beat "
        f"'Income taxes' priority ({lp_taxes})"
    )


# ── BL-044: TEP / Euronext "1st half-year YYYY" header format ────────────────

def test_first_half_year_header_in_markdown_table():
    """'1st half-year 2025' / '2nd half-year 2024' headers in markdown tables
    must be identified as H1-2025 / H2-2024 respectively.

    Euronext-listed companies (e.g. Teleperformance) use this ordinal format
    in their HALF-YEAR FINANCIAL REPORT PDFs → clean.md pipe tables.
    """
    table = (
        "|  | 1st half-year 2025 | 1st half-year 2024 |\n"
        "| --- | --- | --- |\n"
        "| Revenues | 5,116 | 5,076 |\n"
        "| Operating profit | 530 | 503 |\n"
        "| Net profit | 249 | 291 |\n"
    )
    fields = extract_from_markdown_table(table, filing_type="interim_report")
    by_period = {(f.label, f.column_header): f.value for f in fields}
    assert by_period.get(("Revenues", "H1-2025")) == 5116.0, (
        f"Expected Revenues H1-2025=5116, got {by_period}"
    )
    assert by_period.get(("Revenues", "H1-2024")) == 5076.0
    assert by_period.get(("Operating profit", "H1-2025")) == 530.0
    assert by_period.get(("Net profit", "H1-2025")) == 249.0
    # Must not create FY2025 or Q2-2025 periods
    assert not any(
        h in {"FY2025", "FY2024", "Q2-2025", "Q2-2024"}
        for _, h in by_period
    ), f"Unexpected period labels: {set(h for _, h in by_period)}"


def test_first_half_year_header_in_text_extractor():
    """'1st half-year YYYY' headers in space-aligned text (PDF output) map to H1.

    TEP SRC_011 (HALF-YEAR FINANCIAL REPORT AT 30 JUNE 2025) contains
    income statement tables with columns labelled '1st half-year 2025'
    and '1st half-year 2024' in the converted .txt file.
    The 'Notes' column before the data columns (containing references like
    '3.1', '5', '6.3') must be filtered out.
    """
    from elsian.extract.html_tables import extract_tables_from_text

    # Minimal replica of TEP's half-year IS in space-aligned text format.
    txt = (
        "HALF-YEAR FINANCIAL REPORT\n"
        "\n"
        "CONDENSED CONSOLIDATED STATEMENT OF INCOME\n"
        "(in millions of euros)         Notes 1st half-year 2025 1st half-year 2024\n"
        "Revenues                       3.1   5,116            5,076\n"
        "Operating profit                     530              503\n"
        "Income tax                     5     -123             -113\n"
        "Net profit                           249              291\n"
        "Earnings per share (in euros)  6.3   4.21             4.85\n"
    )
    fields = extract_tables_from_text(txt, source_filename="TEP_H1_2025.txt")
    by_period = {(f.label, f.column_header): f.value for f in fields}
    # Revenue: 5,116 (H1-2025) and 5,076 (H1-2024) — note "3.1" must be filtered
    assert by_period.get(("Revenues", "H1-2025")) == 5116.0, (
        f"Revenues H1-2025 expected 5116, got {by_period}"
    )
    assert by_period.get(("Revenues", "H1-2024")) == 5076.0
    assert by_period.get(("Operating profit", "H1-2025")) == 530.0
    assert by_period.get(("Operating profit", "H1-2024")) == 503.0
    # Income tax: note "5" must be filtered, leaving -123 (H1-2025) and -113 (H1-2024)
    assert by_period.get(("Income tax", "H1-2025")) == -123.0
    assert by_period.get(("Income tax", "H1-2024")) == -113.0
    # Earnings per share: note "6.3" must be filtered, leaving 4.21 and 4.85
    eps_h1_25 = by_period.get(("Earnings per share (in euros)", "H1-2025"))
    assert eps_h1_25 == 4.21, f"EPS H1-2025 expected 4.21 (not 6.3), got {eps_h1_25}"
    assert by_period.get(("Earnings per share (in euros)", "H1-2024")) == 4.85
    # Must NOT produce FY2025 from the ordinal year embedded in the header
    assert ("Revenues", "FY2025") not in by_period


def test_half_year_date_header_in_text_extractor():
    """'6/30/2025' date headers in a half-year financial report map to H1-2025
    (not Q2-2025) when the file is identified as a half-year document.
    """
    from elsian.extract.html_tables import extract_tables_from_text

    txt = (
        "HALF-YEAR FINANCIAL REPORT\n"
        "\n"
        "CONDENSED CONSOLIDATED STATEMENT OF FINANCIAL POSITION\n"
        "(in millions of euros)         Notes  6/30/2025  12/31/2024\n"
        "Total assets                          12,095     12,074\n"
        "Total equity                          3,951      4,556\n"
        "Cash and cash equivalents             1,227      1,058\n"
    )
    fields = extract_tables_from_text(txt, source_filename="TEP_H1_2025.txt")
    by_period = {(f.label, f.column_header): f.value for f in fields}
    # June 30 date in a half-year report means H1 balance sheet
    assert by_period.get(("Total assets", "H1-2025")) == 12095.0, (
        f"Expected Total assets H1-2025=12095, got {by_period}"
    )
    assert by_period.get(("Total equity", "H1-2025")) == 3951.0
    # December 31 stays as FY
    assert by_period.get(("Total assets", "FY2024")) == 12074.0
    # Must NOT produce Q2-2025
    assert ("Total assets", "Q2-2025") not in by_period
