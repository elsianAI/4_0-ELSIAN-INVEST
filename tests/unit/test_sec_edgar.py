"""Tests for elsian.acquire.sec_edgar — helpers only (no network calls)."""

import pytest

from elsian.acquire.sec_edgar import (
    _quarter_for_month,
    _period_from_doc_or_date,
    _build_doc_url,
    _build_index_json_url,
    _strip_html_to_text,
    _FilingRecord,
    SecEdgarFetcher,
    ANNUAL_FORMS,
    PERIODIC_FORMS,
)
from elsian.acquire.base import Fetcher


class TestQuarterForMonth:
    @pytest.mark.parametrize("month,expected", [
        (1, "Q1"), (3, "Q1"),
        (4, "Q2"), (6, "Q2"),
        (7, "Q3"), (9, "Q3"),
        (10, "Q4"), (12, "Q4"),
    ])
    def test_quarters(self, month, expected):
        assert _quarter_for_month(month) == expected


class TestPeriodFromDocOrDate:
    def test_annual_from_doc(self):
        result = _period_from_doc_or_date(
            "tzoo-20240101.htm", "2024-03-15", "10-K"
        )
        assert result == "FY2024"

    def test_quarterly_from_date(self):
        result = _period_from_doc_or_date(
            "nodate.htm", "2024-05-10", "10-Q"
        )
        assert result == "Q2-2024"

    def test_20f_annual(self):
        result = _period_from_doc_or_date(
            "gct-20231231.htm", "2024-04-15", "20-F"
        )
        assert result == "FY2023"

    def test_fallback_to_filing_date(self):
        result = _period_from_doc_or_date(
            "nodate.htm", "2024-03-15", "8-K"
        )
        assert result == "2024-03-15"


class TestBuildUrls:
    def test_doc_url(self):
        url = _build_doc_url(12345, "000123456789012345", "filing.htm")
        assert url == "https://www.sec.gov/Archives/edgar/data/12345/000123456789012345/filing.htm"

    def test_index_url(self):
        url = _build_index_json_url(12345, "000123456789012345")
        assert url == "https://www.sec.gov/Archives/edgar/data/12345/000123456789012345/index.json"


class TestStripHtml:
    def test_basic(self):
        result = _strip_html_to_text("<html><body><p>Hello</p><script>evil</script></body></html>")
        assert "Hello" in result
        assert "evil" not in result

    def test_empty(self):
        result = _strip_html_to_text("")
        assert result == ""


class TestFilingRecord:
    def test_accession_nodash(self):
        rec = _FilingRecord("10-K", "2024-01-01", "0001-23-456789", "doc.htm")
        assert rec.accession_nodash == "000123456789"


class TestSecEdgarFetcherIsAFetcher:
    def test_is_fetcher(self):
        assert issubclass(SecEdgarFetcher, Fetcher)


class TestFormSets:
    def test_annual_forms(self):
        assert "10-K" in ANNUAL_FORMS
        assert "20-F" in ANNUAL_FORMS
        assert "40-F" in ANNUAL_FORMS

    def test_periodic_forms(self):
        assert "10-Q" in PERIODIC_FORMS
        assert "6-K" in PERIODIC_FORMS