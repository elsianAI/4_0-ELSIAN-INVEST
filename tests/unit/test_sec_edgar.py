"""Tests for elsian.acquire.sec_edgar — helpers only (no network calls)."""

import pytest
import requests
from unittest.mock import MagicMock

from elsian.acquire.sec_edgar import (
    _quarter_for_month,
    _period_from_doc_or_date,
    _build_doc_url,
    _build_index_json_url,
    _strip_html_to_text,
    _find_exhibit_99,
    _FilingRecord,
    SecClient,
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


# ── CaseConfig.cik tests ────────────────────────────────────────────

import json
from elsian.models.case import CaseConfig


class TestCaseConfigCik:
    def test_cik_from_json(self, tmp_path):
        case_json = tmp_path / "case.json"
        case_json.write_text(json.dumps({
            "ticker": "NVDA",
            "cik": "1045810",
            "source_hint": "sec",
        }))
        cfg = CaseConfig.from_file(tmp_path)
        assert cfg.cik == "1045810"
        assert cfg.ticker == "NVDA"

    def test_cik_none_when_absent(self, tmp_path):
        case_json = tmp_path / "case.json"
        case_json.write_text(json.dumps({
            "ticker": "TZOO",
            "source_hint": "sec",
        }))
        cfg = CaseConfig.from_file(tmp_path)
        assert cfg.cik is None


# ── Cache logical filing count ───────────────────────────────────────

from elsian.models.result import AcquisitionResult


class TestCacheLogicalCount:
    def test_three_files_one_logical_filing(self, tmp_path):
        """SRC_001 with .htm, .txt, .clean.md should count as 1 logical filing."""
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001_annual_FY2025.htm").write_text("html")
        (filings_dir / "SRC_001_annual_FY2025.txt").write_text("text")
        (filings_dir / "SRC_001_annual_FY2025.clean.md").write_text("md")

        case = CaseConfig(ticker="TEST", case_dir=str(tmp_path))
        fetcher = SecEdgarFetcher()
        result = fetcher.acquire(case)

        assert result.filings_downloaded == 1
        assert "cached" in (result.notes or "").lower()

    def test_two_filings_multiple_files(self, tmp_path):
        """Two distinct SRC_ filings with multiple formats each."""
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001_annual_FY2025.htm").write_text("html")
        (filings_dir / "SRC_001_annual_FY2025.txt").write_text("text")
        (filings_dir / "SRC_002_annual_FY2024.htm").write_text("html")
        (filings_dir / "SRC_002_annual_FY2024.txt").write_text("text")
        (filings_dir / "SRC_002_annual_FY2024.clean.md").write_text("md")

        case = CaseConfig(ticker="TEST", case_dir=str(tmp_path))
        fetcher = SecEdgarFetcher()
        result = fetcher.acquire(case)

        assert result.filings_downloaded == 2


# ── _find_exhibit_99 tests ───────────────────────────────────────────

def _make_rec(
    accession: str = "0001234567-24-000001",
    form: str = "8-K",
    primary_doc: str = "primary.htm",
) -> _FilingRecord:
    """Helper: create a minimal _FilingRecord for testing."""
    return _FilingRecord(
        form=form,
        filing_date="2024-03-15",
        accession=accession,
        primary_doc=primary_doc,
    )


def _mock_client(index_json: dict) -> MagicMock:
    """Helper: create a mock SecClient whose get_json returns *index_json*."""
    client = MagicMock(spec=SecClient)
    client.get_json.return_value = index_json
    return client


def _wrap_items(*items: dict) -> dict:
    """Wrap item dicts into the EDGAR index.json structure."""
    return {"directory": {"item": list(items)}}


class TestFindExhibit99:
    """Unit tests for _find_exhibit_99 — BL-030."""

    # (a) Match by EDGAR document type "EX-99.1"
    def test_find_exhibit_99_ex991_by_type(self):
        idx = _wrap_items(
            {"name": "primary.htm", "type": "8-K"},
            {"name": "earningsrelease.htm", "type": "EX-99.1"},
        )
        client = _mock_client(idx)
        rec = _make_rec()
        result = _find_exhibit_99(client, 12345, rec)
        assert result == "earningsrelease.htm"

    # (b) Match by filename pattern when no type tag
    def test_find_exhibit_99_by_filename_pattern(self):
        idx = _wrap_items(
            {"name": "primary.htm", "type": "8-K"},
            {"name": "exhibit99-1.htm", "type": ""},
        )
        client = _mock_client(idx)
        rec = _make_rec()
        result = _find_exhibit_99(client, 12345, rec)
        assert result == "exhibit99-1.htm"

    # (c) No exhibits → returns None
    def test_find_exhibit_99_no_match(self):
        idx = _wrap_items(
            {"name": "primary.htm", "type": "8-K"},
            {"name": "R9999.htm", "type": "GRAPHIC"},
        )
        client = _mock_client(idx)
        rec = _make_rec()
        result = _find_exhibit_99(client, 12345, rec)
        assert result is None

    # (d) Skips index/header files even if they match filename pattern
    def test_find_exhibit_99_skips_index_files(self):
        idx = _wrap_items(
            {"name": "index.htm", "type": ""},
            {"name": "filing-index.htm", "type": ""},
            {"name": "header.htm", "type": ""},
            {"name": "ex99-1press.htm", "type": "EX-99.1"},
        )
        client = _mock_client(idx)
        rec = _make_rec()
        result = _find_exhibit_99(client, 12345, rec)
        assert result == "ex99-1press.htm"

    # (e) Match EX-99.2 type (some issuers use this)
    def test_find_exhibit_99_ex992_type(self):
        idx = _wrap_items(
            {"name": "primary.htm", "type": "8-K"},
            {"name": "supplemental.htm", "type": "EX-99.2"},
        )
        client = _mock_client(idx)
        rec = _make_rec()
        result = _find_exhibit_99(client, 12345, rec)
        assert result == "supplemental.htm"

    # (f) PDF exhibit — should be returned (extension is allowed)
    def test_find_exhibit_99_pdf_exhibit(self):
        idx = _wrap_items(
            {"name": "primary.htm", "type": "8-K"},
            {"name": "exhibit99.pdf", "type": "EX-99.1"},
        )
        client = _mock_client(idx)
        rec = _make_rec()
        result = _find_exhibit_99(client, 12345, rec)
        assert result == "exhibit99.pdf"

    # (g) API error → graceful None
    def test_find_exhibit_99_api_error(self):
        client = MagicMock(spec=SecClient)
        client.get_json.side_effect = ConnectionError("network failure")
        rec = _make_rec()
        result = _find_exhibit_99(client, 12345, rec)
        assert result is None

    # ── Additional edge-case tests ───────────────────────────────────

    def test_find_exhibit_99_ex99_bare_type(self):
        """Match EX-99 bare type (no .1/.2 suffix)."""
        idx = _wrap_items(
            {"name": "earnings.htm", "type": "EX-99"},
        )
        client = _mock_client(idx)
        result = _find_exhibit_99(client, 12345, _make_rec())
        assert result == "earnings.htm"

    def test_find_exhibit_99_filename_ex_99_underscore(self):
        """Filename pattern with underscore: ex_99_1.htm."""
        idx = _wrap_items(
            {"name": "ex_99_1.htm", "type": ""},
        )
        client = _mock_client(idx)
        result = _find_exhibit_99(client, 12345, _make_rec())
        assert result == "ex_99_1.htm"

    def test_find_exhibit_99_skips_image_extension(self):
        """Files with non-document extensions (e.g. .jpg) are ignored."""
        idx = _wrap_items(
            {"name": "exhibit99.jpg", "type": ""},
            {"name": "exhibit99chart.png", "type": "GRAPHIC"},
        )
        client = _mock_client(idx)
        result = _find_exhibit_99(client, 12345, _make_rec())
        assert result is None

    def test_find_exhibit_99_empty_index(self):
        """Empty directory items → None."""
        idx = {"directory": {"item": []}}
        client = _mock_client(idx)
        result = _find_exhibit_99(client, 12345, _make_rec())
        assert result is None


# ── BL-066: SecClient retries counter ────────────────────────────────

class TestSecClientRetries:
    def test_retries_starts_at_zero(self):
        client = SecClient()
        assert client.retries == 0

    def test_retries_increments_on_retry(self, monkeypatch):
        """Simulate a 503 response followed by success; retries should be 1."""
        import time as time_module
        monkeypatch.setattr(time_module, "sleep", lambda _: None)

        call_count = 0

        def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                err_resp = MagicMock()
                err_resp.status_code = 503
                exc = requests.exceptions.HTTPError(response=err_resp)
                raise exc
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.encoding = "utf-8"
            return resp

        client = SecClient()
        import unittest.mock as _mock
        with _mock.patch.object(client._session, "get", side_effect=fake_get):
            client.get("https://example.com/")

        assert client.retries == 1


# ── BL-066: resolve_cik uses load_json_ttl with cache_hit ────────────

class TestResolveCikCacheHit:
    def test_resolve_cik_returns_tuple_with_cache_flag(self, monkeypatch):
        """resolve_cik returns (result, cache_hit) where cache_hit is a bool."""
        payload = {"0": {"ticker": "TZOO", "cik_str": "1375966"}}

        import unittest.mock as _mock
        from elsian.acquire.sec_edgar import resolve_cik

        client = SecClient()

        with _mock.patch(
            "elsian.acquire.sec_edgar.load_json_ttl",
            return_value=(payload, True),
        ):
            result, hit = resolve_cik(client, "TZOO")

        assert result == (1375966, "0001375966")
        assert hit is True

    def test_resolve_cik_miss_returns_false_cache_flag(self, monkeypatch):
        payload = {}
        import unittest.mock as _mock
        from elsian.acquire.sec_edgar import resolve_cik

        client = SecClient()

        with _mock.patch(
            "elsian.acquire.sec_edgar.load_json_ttl",
            return_value=(payload, False),
        ):
            result, hit = resolve_cik(client, "ZZZNONE")

        assert result is None
        assert hit is False


# ── BL-066: AcquisitionResult cache_hit in SEC cached path ───────────

class TestSecEdgarCacheHitField:
    def test_cached_filings_set_cache_hit_true(self, tmp_path):
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001_10-K_FY2024.htm").write_text("html")
        (filings_dir / "SRC_001_10-K_FY2024.txt").write_text("text")

        case = CaseConfig(ticker="TZOO", case_dir=str(tmp_path))
        fetcher = SecEdgarFetcher()
        result = fetcher.acquire(case)

        assert result.cache_hit is True
        assert result.source_kind == "filing"


    def test_find_exhibit_99_malformed_index(self):
        """Index JSON without 'directory' key → None."""
        client = _mock_client({})
        result = _find_exhibit_99(client, 12345, _make_rec())
        assert result is None

    def test_find_exhibit_99_returns_first_match(self):
        """Multiple matching exhibits → returns the first one encountered."""
        idx = _wrap_items(
            {"name": "ex99-1.htm", "type": "EX-99.1"},
            {"name": "ex99-2.htm", "type": "EX-99.2"},
        )
        client = _mock_client(idx)
        result = _find_exhibit_99(client, 12345, _make_rec())
        assert result == "ex99-1.htm"

    def test_find_exhibit_99_txt_extension(self):
        """Exhibit with .txt extension should be matched."""
        idx = _wrap_items(
            {"name": "ex99-1.txt", "type": "EX-99.1"},
        )
        client = _mock_client(idx)
        result = _find_exhibit_99(client, 12345, _make_rec())
        assert result == "ex99-1.txt"