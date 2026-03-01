"""Tests for elsian.convert.html_to_markdown."""

import tempfile
from pathlib import Path

import pytest

from elsian.convert.html_to_markdown import (
    _table_to_markdown,
    _is_clean_md_useful,
    convert,
    SECTION_PATTERNS,
)
from bs4 import BeautifulSoup, Tag


class TestTableToMarkdown:
    """Tests for _table_to_markdown."""

    def test_basic_table(self):
        html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        md = _table_to_markdown(table)
        assert "| A | B |" in md
        assert "| 1 | 2 |" in md

    def test_empty_table(self):
        html = "<table></table>"
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        md = _table_to_markdown(table)
        assert md == ""

    def test_uneven_rows(self):
        html = "<table><tr><td>A</td><td>B</td><td>C</td></tr><tr><td>1</td></tr></table>"
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        md = _table_to_markdown(table)
        assert md.count("|") > 0  # padded


class TestIsMdUseful:
    """Tests for _is_clean_md_useful."""

    def test_empty(self):
        assert not _is_clean_md_useful("")

    def test_no_sections(self):
        assert not _is_clean_md_useful("Just some text without financial data")

    def test_valid_content(self):
        text = (
            "## INCOME STATEMENT\n\n### Revenue\n| Item | 2024 |\n|---|---|\n"
            + "\n".join(f"| Row {i} | {1000+i} |" for i in range(15))
        )
        assert _is_clean_md_useful(text)


class TestSectionPatterns:
    """Test that section patterns match expected headings."""

    @pytest.mark.parametrize("heading,expected_key", [
        ("Consolidated Balance Sheet", "balance_sheet"),
        ("CONSOLIDATED STATEMENTS OF FINANCIAL POSITION", "balance_sheet"),
        ("Consolidated Statements of Income", "income_statement"),
        ("Consolidated Statements of Operations", "income_statement"),
        ("Consolidated Statements of Cash Flows", "cash_flow"),
        ("Consolidated Statements of Stockholders' Equity", "equity"),
    ])
    def test_pattern_match(self, heading, expected_key):
        matched = False
        for key, pattern in SECTION_PATTERNS:
            if key == expected_key and pattern.search(heading):
                matched = True
                break
        assert matched, f"Pattern {expected_key} did not match '{heading}'"


class TestConvert:
    """Tests for the convert function."""

    def test_convert_with_financial_tables(self):
        html = """<html><body>
        <p><b>Consolidated Statements of Income</b></p>
        <table>
            <tr><th></th><th>2024</th><th>2023</th></tr>
            <tr><td>Revenue</td><td>1,000,000</td><td>900,000</td></tr>
            <tr><td>Cost of revenue</td><td>500,000</td><td>450,000</td></tr>
            <tr><td>Net income</td><td>200,000</td><td>180,000</td></tr>
        </table>
        <p><b>Consolidated Balance Sheet</b></p>
        <table>
            <tr><th></th><th>2024</th><th>2023</th></tr>
            <tr><td>Total assets</td><td>5,000,000</td><td>4,500,000</td></tr>
            <tr><td>Total liabilities</td><td>2,000,000</td><td>1,800,000</td></tr>
            <tr><td>Total equity</td><td>3,000,000</td><td>2,700,000</td></tr>
        </table>
        </body></html>"""

        with tempfile.NamedTemporaryFile(suffix=".htm", mode="w", delete=False) as f:
            f.write(html)
            f.flush()
            result = convert(Path(f.name))

        assert "INCOME STATEMENT" in result
        assert "BALANCE SHEET" in result
        assert "1,000,000" in result

    def test_convert_empty_html(self):
        with tempfile.NamedTemporaryFile(suffix=".htm", mode="w", delete=False) as f:
            f.write("<html><body>Nothing here</body></html>")
            f.flush()
            result = convert(Path(f.name))
        assert result == ""