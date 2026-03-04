"""Tests for elsian.extract.pdf_tables — structured PDF table extraction.

Uses mocked pdfplumber responses to test financial table detection,
value parsing, period detection, and provenance population without
requiring actual PDF files.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from elsian.extract.pdf_tables import (
    TableField,
    _detect_section,
    _extract_column_headers,
    _is_financial_table,
    _parse_cell_value,
    _parse_period_from_header,
    extract_tables_from_pdf,
)


# ── Helper: build a mock pdfplumber PDF ──────────────────────────────

def _mock_pdfplumber_open(pages_data: list[dict]) -> MagicMock:
    """Return a mock pdfplumber.open() context manager.

    Args:
        pages_data: List of dicts, each with:
            - "tables": list of 2D tables (list[list[str|None]])
            - "text": optional page text string
    """
    mock_pdf = MagicMock()
    mock_pages = []
    for pd in pages_data:
        page = MagicMock()
        page.extract_tables.return_value = pd.get("tables", [])
        page.extract_text.return_value = pd.get("text", "")
        mock_pages.append(page)
    mock_pdf.pages = mock_pages
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    return mock_pdf


class TestParseValueCell(unittest.TestCase):
    """Test _parse_cell_value for PDF table cells."""

    def test_plain_integer(self) -> None:
        self.assertEqual(_parse_cell_value("1234"), 1234.0)

    def test_thousands_separator(self) -> None:
        self.assertEqual(_parse_cell_value("1,234,567"), 1234567.0)

    def test_parenthetical_negative(self) -> None:
        self.assertEqual(_parse_cell_value("(1,234)"), -1234.0)

    def test_dash_returns_none(self) -> None:
        self.assertIsNone(_parse_cell_value("—"))
        self.assertIsNone(_parse_cell_value("–"))
        self.assertIsNone(_parse_cell_value("-"))

    def test_currency_prefix(self) -> None:
        self.assertEqual(_parse_cell_value("$1,234"), 1234.0)
        self.assertEqual(_parse_cell_value("€500"), 500.0)
        self.assertEqual(_parse_cell_value("£750"), 750.0)

    def test_blank_cell(self) -> None:
        self.assertIsNone(_parse_cell_value(""))
        self.assertIsNone(_parse_cell_value("   "))

    def test_none_cell(self) -> None:
        self.assertIsNone(_parse_cell_value(None))  # type: ignore[arg-type]

    def test_decimal_value(self) -> None:
        self.assertAlmostEqual(_parse_cell_value("1.23"), 1.23)

    def test_negative_with_minus(self) -> None:
        self.assertEqual(_parse_cell_value("-500"), -500.0)


class TestParsePeriodFromHeader(unittest.TestCase):
    """Test _parse_period_from_header for column header period detection."""

    def test_bare_year(self) -> None:
        self.assertEqual(_parse_period_from_header("2024"), "FY2024")

    def test_fy_prefix(self) -> None:
        self.assertEqual(_parse_period_from_header("FY2024"), "FY2024")
        self.assertEqual(_parse_period_from_header("FY 2023"), "FY2023")

    def test_year_ended(self) -> None:
        self.assertEqual(
            _parse_period_from_header("Year ended December 31, 2024"),
            "FY2024",
        )

    def test_twelve_months_ended(self) -> None:
        self.assertEqual(
            _parse_period_from_header("Twelve months ended 31 December 2023"),
            "FY2023",
        )

    def test_half_year(self) -> None:
        self.assertEqual(
            _parse_period_from_header("Six months ended June 30, 2024"),
            "H12024",
        )

    def test_half_year_french(self) -> None:
        self.assertEqual(
            _parse_period_from_header("Six months ended 30 Juin 2024"),
            "H12024",
        )

    def test_h1_prefix(self) -> None:
        self.assertEqual(_parse_period_from_header("H1 2024"), "H12024")

    def test_q_prefix(self) -> None:
        self.assertEqual(_parse_period_from_header("Q3 2024"), "Q32024")

    def test_empty_header(self) -> None:
        self.assertEqual(_parse_period_from_header(""), "")

    def test_no_year(self) -> None:
        self.assertEqual(_parse_period_from_header("Total"), "")


class TestIsFinancialTable(unittest.TestCase):
    """Test _is_financial_table for detecting financial vs non-financial tables."""

    def test_income_statement_table(self) -> None:
        table = [
            ["", "2024", "2023"],
            ["Revenue", "1,000", "900"],
            ["Net income", "200", "180"],
        ]
        self.assertTrue(_is_financial_table(table))

    def test_balance_sheet_table(self) -> None:
        table = [
            ["", "2024", "2023"],
            ["Total assets", "5,000", "4,500"],
            ["Total equity", "2,000", "1,800"],
        ]
        self.assertTrue(_is_financial_table(table))

    def test_non_financial_table(self) -> None:
        table = [
            ["Name", "Role", "Age"],
            ["John Smith", "CEO", "55"],
            ["Jane Doe", "CFO", "48"],
        ]
        self.assertFalse(_is_financial_table(table))

    def test_empty_table(self) -> None:
        self.assertFalse(_is_financial_table([]))

    def test_single_row(self) -> None:
        self.assertFalse(_is_financial_table([["Revenue", "1000"]]))

    def test_table_no_numbers(self) -> None:
        table = [
            ["Description", "Status"],
            ["Revenue recognition", "Adopted"],
            ["Lease accounting", "In progress"],
        ]
        self.assertFalse(_is_financial_table(table))


class TestDetectSection(unittest.TestCase):
    """Test _detect_section for financial statement classification."""

    def test_income_statement(self) -> None:
        table = [["Consolidated Statement of Income", "", ""], ["Revenue", "100", "90"]]
        self.assertEqual(_detect_section(table), "income_statement")

    def test_balance_sheet(self) -> None:
        table = [["Consolidated Balance Sheet", "", ""], ["Total assets", "500", "400"]]
        self.assertEqual(_detect_section(table), "balance_sheet")

    def test_cash_flow(self) -> None:
        table = [["Cash Flow Statement", "", ""], ["Cash generated", "50", "40"]]
        self.assertEqual(_detect_section(table), "cash_flow")

    def test_page_text_context(self) -> None:
        table = [["", "2024", "2023"], ["Revenue", "100", "90"]]
        self.assertEqual(
            _detect_section(table, page_text="Statement of Financial Position"),
            "balance_sheet",
        )

    def test_fallback(self) -> None:
        table = [["", "2024", "2023"], ["Total", "100", "90"]]
        self.assertEqual(_detect_section(table), "financial")


class TestExtractColumnHeaders(unittest.TestCase):
    """Test _extract_column_headers for period extraction from table headers."""

    def test_simple_year_headers(self) -> None:
        table = [
            ["", "2024", "2023"],
            ["Revenue", "1000", "900"],
        ]
        headers, data_start = _extract_column_headers(table)
        self.assertEqual(headers, ["", "2024", "2023"])
        self.assertEqual(data_start, 1)

    def test_multi_row_headers(self) -> None:
        table = [
            ["", "Year ended", "Year ended"],
            ["", "Dec 31, 2024", "Dec 31, 2023"],
            ["Revenue", "1000", "900"],
        ]
        headers, data_start = _extract_column_headers(table)
        # Should combine the two header rows
        self.assertIn("2024", " ".join(headers))
        self.assertGreaterEqual(data_start, 1)


class TestExtractTablesFromPdf(unittest.TestCase):
    """Integration tests for extract_tables_from_pdf with mocked pdfplumber."""

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_income_statement_extraction(self, mock_plumber: MagicMock) -> None:
        """Extract revenue and net income from a simple IS table."""
        table = [
            ["", "2024", "2023"],
            ["Revenue", "83,902", "72,100"],
            ["Cost of revenue", "35,000", "30,000"],
            ["Net income", "12,500", "10,200"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": "Statement of Income"}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")

        self.assertGreater(len(results), 0)
        # Check that we got fields for both periods
        periods = {tf.column_header for tf in results}
        self.assertIn("FY2024", periods)
        self.assertIn("FY2023", periods)

        # Check revenue was extracted
        revenue_fields = [tf for tf in results if "Revenue" in tf.label and tf.column_header == "FY2024"]
        self.assertEqual(len(revenue_fields), 1)
        self.assertEqual(revenue_fields[0].value, 83902.0)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_balance_sheet_extraction(self, mock_plumber: MagicMock) -> None:
        """Extract assets and equity from a BS table."""
        table = [
            ["", "2024", "2023"],
            ["Total assets", "500,000", "450,000"],
            ["Total liabilities", "300,000", "270,000"],
            ["Total equity", "200,000", "180,000"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": "Balance Sheet"}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")

        labels = {tf.label for tf in results}
        self.assertIn("Total assets", labels)
        self.assertIn("Total equity", labels)

        assets = [tf for tf in results if tf.label == "Total assets" and tf.column_header == "FY2024"]
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].value, 500000.0)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_cash_flow_extraction(self, mock_plumber: MagicMock) -> None:
        """Extract cash flow fields from a CF table."""
        table = [
            ["Cash Flow Statement", "2024", "2023"],
            ["Cash from operating activities", "25,000", "22,000"],
            ["Capital expenditures", "(8,000)", "(7,500)"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": ""}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")

        capex = [tf for tf in results if "Capital expenditures" in tf.label and tf.column_header == "FY2024"]
        self.assertEqual(len(capex), 1)
        self.assertEqual(capex[0].value, -8000.0)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_non_financial_table_skipped(self, mock_plumber: MagicMock) -> None:
        """Non-financial tables produce no results."""
        table = [
            ["Director", "Role", "Since"],
            ["Alice", "Chair", "2020"],
            ["Bob", "VP", "2018"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": "Board of Directors"}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        self.assertEqual(len(results), 0)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_empty_pdf_no_tables(self, mock_plumber: MagicMock) -> None:
        """PDF with no tables returns empty list."""
        mock_pdf = _mock_pdfplumber_open([{"tables": [], "text": "Some text"}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        self.assertEqual(results, [])

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_provenance_l2_populated(self, mock_plumber: MagicMock) -> None:
        """Verify Provenance L2 fields on returned TableField."""
        table = [
            ["", "2024", "2023"],
            ["Revenue", "1,000", "900"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": "Income Statement"}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        self.assertGreater(len(results), 0)

        tf = results[0]
        # Table index: page 0 * 100 + table 0 = 0
        self.assertEqual(tf.table_index, 0)
        self.assertIn("income_statement", tf.table_title)
        self.assertEqual(tf.label, "Revenue")
        self.assertTrue(tf.raw_text)  # raw_text populated
        self.assertTrue(tf.col_label)  # col_label populated
        self.assertGreaterEqual(tf.row_idx, 0)
        self.assertGreaterEqual(tf.col_idx, 0)
        # source_location has pdf_tbl marker
        self.assertIn("pdf_tbl", tf.source_location)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_extraction_method_in_source_location(self, mock_plumber: MagicMock) -> None:
        """source_location contains 'pdf_tbl' for extraction_method detection."""
        table = [
            ["", "2024"],
            ["Revenue", "500"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": ""}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        self.assertGreater(len(results), 0)
        for tf in results:
            self.assertIn("pdf_tbl", tf.source_location)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_table_with_no_numeric_values_skipped(self, mock_plumber: MagicMock) -> None:
        """A table-shaped block with no parseable numbers is skipped."""
        table = [
            ["Item", "2024", "2023"],
            ["Revenue recognition policy", "Adopted", "In progress"],
            ["Lease standard", "Applied", "N/A"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": ""}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        self.assertEqual(results, [])

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_parenthetical_negative_values(self, mock_plumber: MagicMock) -> None:
        """Parenthetical negatives are parsed correctly."""
        table = [
            ["", "2024"],
            ["Net income (loss)", "(5,432)"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": "Income"}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, -5432.0)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_multi_page_extraction(self, mock_plumber: MagicMock) -> None:
        """Tables from multiple pages are extracted with unique table_index."""
        table1 = [
            ["", "2024"],
            ["Revenue", "1,000"],
        ]
        table2 = [
            ["", "2024"],
            ["Total assets", "5,000"],
        ]
        mock_pdf = _mock_pdfplumber_open([
            {"tables": [table1], "text": "Income Statement"},
            {"tables": [table2], "text": "Balance Sheet"},
        ])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        self.assertGreater(len(results), 1)

        # Different pages should have different table_index
        indices = {tf.table_index for tf in results}
        self.assertEqual(len(indices), 2)
        # Page 0 table 0 = 0, Page 1 table 0 = 100
        self.assertIn(0, indices)
        self.assertIn(100, indices)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_filing_source_id_in_source_location(self, mock_plumber: MagicMock) -> None:
        """filing_source_id appears in every TableField's source_location."""
        table = [
            ["", "2024"],
            ["Revenue", "500"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": ""}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_007_annual_FY2024.txt")
        self.assertGreater(len(results), 0)
        for tf in results:
            self.assertIn("SRC_007_annual_FY2024.txt", tf.source_location)

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_column_header_year_ended(self, mock_plumber: MagicMock) -> None:
        """Column headers with 'Year ended ...' produce FY period keys."""
        table = [
            ["", "Year ended December 31, 2024", "Year ended December 31, 2023"],
            ["Revenue", "1,000", "900"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": ""}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        periods = {tf.column_header for tf in results}
        self.assertIn("FY2024", periods)
        self.assertIn("FY2023", periods)

    def test_pdfplumber_unavailable(self) -> None:
        """When pdfplumber is None, extract_tables_from_pdf returns empty list."""
        import elsian.extract.pdf_tables as mod
        original = mod.pdfplumber
        try:
            mod.pdfplumber = None
            result = extract_tables_from_pdf("/tmp/nonexistent.pdf")
            self.assertEqual(result, [])
        finally:
            mod.pdfplumber = original

    @patch("elsian.extract.pdf_tables.pdfplumber")
    def test_table_no_period_headers_skipped(self, mock_plumber: MagicMock) -> None:
        """A financial table without parseable period headers yields nothing."""
        table = [
            ["Item", "Description", "Notes"],
            ["Revenue", "1,000", "See note 3"],
            ["Net income", "200", "See note 5"],
        ]
        mock_pdf = _mock_pdfplumber_open([{"tables": [table], "text": ""}])
        mock_plumber.open.return_value = mock_pdf

        results = extract_tables_from_pdf("/tmp/test.pdf", "SRC_001.txt")
        # "Description" and "Notes" are not periods, so no results
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
