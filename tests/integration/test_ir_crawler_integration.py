"""Integration tests for IR crawler integrated into EuRegulatorsFetcher.

Tests verify that:
1. IR crawler is called when filings_sources is empty and web_ir is set.
2. IR crawler is NOT called when filings_sources has entries.
3. _acquire_via_ir_crawler works correctly with mocked crawler functions.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from elsian.acquire.eu_regulators import EuRegulatorsFetcher
from elsian.models.case import CaseConfig


# ── Helpers ────────────────────────────────────────────────────────────

def _make_case_dir(
    ticker: str = "TEST",
    web_ir: str = "",
    filings_sources: Optional[list[dict[str, Any]]] = None,
    market: str = "",
    extra_fields: Optional[dict[str, Any]] = None,
) -> tempfile.TemporaryDirectory:
    """Create a temp directory with case.json for testing."""
    td = tempfile.TemporaryDirectory()
    case_data: dict[str, Any] = {"ticker": ticker}
    if web_ir:
        case_data["web_ir"] = web_ir
    if filings_sources is not None:
        case_data["filings_sources"] = filings_sources
    if market:
        case_data["market"] = market
    if extra_fields:
        case_data.update(extra_fields)
    Path(td.name, "case.json").write_text(json.dumps(case_data), encoding="utf-8")
    Path(td.name, "filings").mkdir()
    return td


def _make_case_config(td_path: str, ticker: str = "TEST") -> CaseConfig:
    return CaseConfig(ticker=ticker, source_hint="eu", case_dir=td_path)


# ── Test: IR crawler NOT called when filings_sources has entries ──────

class TestIrCrawlerNotCalledWithSources:
    """When filings_sources is declared, IR crawler should NOT activate."""

    def test_sources_present_skips_ir_crawler(self) -> None:
        td = _make_case_dir(
            ticker="TEP",
            filings_sources=[
                {"url": "https://example.com/report.pdf", "filename": "report.pdf"},
            ],
            web_ir="https://www.tp.com/investors",
        )
        with td:
            case = _make_case_config(td.name, "TEP")
            fetcher = EuRegulatorsFetcher()

            with patch.object(
                fetcher, "_acquire_via_ir_crawler", return_value=0
            ) as mock_ir:
                # Patch _download_sources to avoid real HTTP
                with patch(
                    "elsian.acquire.eu_regulators._download_sources", return_value=0
                ):
                    fetcher.acquire(case)

            # IR crawler should NOT have been called (sources exist)
            mock_ir.assert_not_called()

    def test_sources_present_even_if_download_fails(self) -> None:
        """IR crawler should not activate even when HTTP download returns 0."""
        td = _make_case_dir(
            ticker="TEP",
            filings_sources=[
                {"url": "https://example.com/report.pdf", "filename": "report.pdf"},
            ],
            web_ir="https://www.tp.com/investors",
        )
        with td:
            case = _make_case_config(td.name, "TEP")
            fetcher = EuRegulatorsFetcher()

            with patch.object(
                fetcher, "_acquire_via_ir_crawler", return_value=0
            ) as mock_ir:
                with patch(
                    "elsian.acquire.eu_regulators._download_sources", return_value=0
                ):
                    fetcher.acquire(case)

            mock_ir.assert_not_called()


# ── Test: IR crawler IS called when no sources and web_ir is set ──────

class TestIrCrawlerCalledWithWebIr:
    """When filings_sources is empty/missing and web_ir is set, IR crawler activates."""

    def test_no_sources_with_web_ir_calls_crawler(self) -> None:
        td = _make_case_dir(
            ticker="TEST",
            web_ir="https://www.example.com/investors",
            filings_sources=[],  # explicitly empty
        )
        with td:
            case = _make_case_config(td.name)
            fetcher = EuRegulatorsFetcher()

            with patch.object(
                fetcher, "_acquire_via_ir_crawler", return_value=3
            ) as mock_ir:
                result = fetcher.acquire(case)

            mock_ir.assert_called_once()
            # Verify args
            args = mock_ir.call_args
            assert args[0][0] == "https://www.example.com/investors"  # web_ir
            assert args[0][1] == "TEST"  # ticker

    def test_missing_sources_with_web_ir_calls_crawler(self) -> None:
        """filings_sources key not present at all."""
        td = _make_case_dir(
            ticker="TEST",
            web_ir="https://www.example.com/investors",
        )
        with td:
            case = _make_case_config(td.name)
            fetcher = EuRegulatorsFetcher()

            with patch.object(
                fetcher, "_acquire_via_ir_crawler", return_value=0
            ) as mock_ir:
                fetcher.acquire(case)

            mock_ir.assert_called_once()

    def test_no_web_ir_does_not_call_crawler(self) -> None:
        """No web_ir → no crawler."""
        td = _make_case_dir(ticker="TEST", filings_sources=[])
        with td:
            case = _make_case_config(td.name)
            fetcher = EuRegulatorsFetcher()

            with patch.object(
                fetcher, "_acquire_via_ir_crawler", return_value=0
            ) as mock_ir:
                fetcher.acquire(case)

            mock_ir.assert_not_called()


# ── Test: IR crawler not called when filings already exist ────────────

class TestIrCrawlerSkipsExistingFilings:
    """If filings dir already has files, IR crawler should not activate."""

    def test_existing_files_skip_crawler(self) -> None:
        td = _make_case_dir(
            ticker="TEST",
            web_ir="https://www.example.com/investors",
            filings_sources=[],
        )
        with td:
            # Pre-populate a filing
            (Path(td.name) / "filings" / "annual.txt").write_text("content")

            case = _make_case_config(td.name)
            fetcher = EuRegulatorsFetcher()

            with patch.object(
                fetcher, "_acquire_via_ir_crawler", return_value=0
            ) as mock_ir:
                fetcher.acquire(case)

            # Should NOT call crawler because files already exist
            mock_ir.assert_not_called()


# ── Test: _acquire_via_ir_crawler with mocked crawler functions ───────

class TestAcquireViaIrCrawlerMocked:
    """Unit-level test of _acquire_via_ir_crawler with all external calls mocked."""

    @patch("elsian.acquire.eu_regulators.resolve_ir_base_url")
    @patch("elsian.acquire.eu_regulators.build_ir_pages")
    @patch("elsian.acquire.eu_regulators.extract_filing_candidates")
    @patch("elsian.acquire.eu_regulators.discover_ir_subpages")
    @patch("elsian.acquire.eu_regulators.select_fallback_candidates")
    @patch("elsian.acquire.eu_regulators._http_get")
    def test_full_flow_mocked(
        self,
        mock_http_get: MagicMock,
        mock_select: MagicMock,
        mock_discover: MagicMock,
        mock_extract: MagicMock,
        mock_build: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        mock_resolve.return_value = "https://www.example.com/investors"
        mock_build.return_value = ["https://www.example.com/investors"]
        mock_discover.return_value = []
        mock_extract.return_value = [
            {
                "url": "https://www.example.com/files/annual-2024.pdf",
                "titulo": "Annual Report 2024",
                "score": 5,
                "tipo_guess": "ANNUAL_REPORT",
                "selection_score": 9.0,
            },
        ]
        mock_select.return_value = [
            {
                "url": "https://www.example.com/files/annual-2024.pdf",
                "titulo": "Annual Report 2024",
                "score": 5,
                "tipo_guess": "ANNUAL_REPORT",
                "selection_score": 9.0,
            },
        ]
        mock_http_get.return_value = b"%PDF-1.4 fake pdf content"

        with tempfile.TemporaryDirectory() as td:
            filings_dir = Path(td) / "filings"
            filings_dir.mkdir()

            fetcher = EuRegulatorsFetcher()

            # Mock _fetch_page_html to return some HTML
            with patch.object(
                fetcher, "_fetch_page_html", return_value="<html><body>test</body></html>"
            ):
                # Mock PDF conversion
                with patch(
                    "elsian.acquire.eu_regulators.extract_pdf_text_from_file",
                    return_value="extracted text",
                ):
                    count = fetcher._acquire_via_ir_crawler(
                        "https://www.example.com/investors",
                        "TEST",
                        filings_dir,
                    )

            assert count == 1
            mock_resolve.assert_called_once()
            mock_build.assert_called_once_with("https://www.example.com/investors")
            mock_select.assert_called_once()
            # PDF file should be written
            pdf_files = list(filings_dir.glob("*.pdf"))
            assert len(pdf_files) == 1

    @patch("elsian.acquire.eu_regulators.resolve_ir_base_url")
    def test_unresolvable_url_returns_zero(
        self, mock_resolve: MagicMock,
    ) -> None:
        mock_resolve.return_value = None

        with tempfile.TemporaryDirectory() as td:
            fetcher = EuRegulatorsFetcher()
            count = fetcher._acquire_via_ir_crawler(
                "https://bogus.example.com/investors",
                "TEST",
                Path(td) / "filings",
            )
            assert count == 0

    @patch("elsian.acquire.eu_regulators.resolve_ir_base_url")
    @patch("elsian.acquire.eu_regulators.build_ir_pages")
    def test_no_pages_returns_zero(
        self,
        mock_build: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        mock_resolve.return_value = "https://www.example.com/investors"
        mock_build.return_value = []

        with tempfile.TemporaryDirectory() as td:
            fetcher = EuRegulatorsFetcher()
            count = fetcher._acquire_via_ir_crawler(
                "https://www.example.com/investors",
                "TEST",
                Path(td) / "filings",
            )
            assert count == 0

    @patch("elsian.acquire.eu_regulators.resolve_ir_base_url")
    @patch("elsian.acquire.eu_regulators.build_ir_pages")
    @patch("elsian.acquire.eu_regulators.extract_filing_candidates")
    @patch("elsian.acquire.eu_regulators.discover_ir_subpages")
    @patch("elsian.acquire.eu_regulators.select_fallback_candidates")
    def test_no_candidates_returns_zero(
        self,
        mock_select: MagicMock,
        mock_discover: MagicMock,
        mock_extract: MagicMock,
        mock_build: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        mock_resolve.return_value = "https://www.example.com/investors"
        mock_build.return_value = ["https://www.example.com/investors"]
        mock_extract.return_value = []
        mock_discover.return_value = []
        mock_select.return_value = []  # shouldn't be called but safe

        with tempfile.TemporaryDirectory() as td:
            filings_dir = Path(td) / "filings"
            filings_dir.mkdir()
            fetcher = EuRegulatorsFetcher()

            with patch.object(
                fetcher, "_fetch_page_html", return_value="<html></html>"
            ):
                count = fetcher._acquire_via_ir_crawler(
                    "https://www.example.com/investors",
                    "TEST",
                    filings_dir,
                )
            assert count == 0


# ── Test: AcquisitionResult includes ir_crawler coverage ──────────────

class TestAcquisitionResultIncludesIrCrawler:
    """Verify AcquisitionResult.coverage includes ir_crawler section."""

    def test_coverage_has_ir_crawler_key(self) -> None:
        td = _make_case_dir(
            ticker="TEST",
            web_ir="https://www.example.com/investors",
            filings_sources=[],
        )
        with td:
            case = _make_case_config(td.name)
            fetcher = EuRegulatorsFetcher()

            with patch.object(
                fetcher, "_acquire_via_ir_crawler", return_value=0
            ):
                result = fetcher.acquire(case)

            assert "ir_crawler" in result.coverage
            assert result.coverage["ir_crawler"]["web_ir"] == "https://www.example.com/investors"

    def test_coverage_ir_crawler_empty_when_no_web_ir(self) -> None:
        td = _make_case_dir(ticker="TEST", filings_sources=[])
        with td:
            case = _make_case_config(td.name)
            fetcher = EuRegulatorsFetcher()
            result = fetcher.acquire(case)
            assert "ir_crawler" in result.coverage
            assert result.coverage["ir_crawler"]["downloaded_new"] == 0


# ── Test: _fetch_page_html ────────────────────────────────────────────

class TestFetchPageHtml:
    """Test the static _fetch_page_html method."""

    def test_returns_none_on_non_200(self) -> None:
        session = MagicMock()
        response = MagicMock()
        response.status_code = 404
        session.get.return_value = response

        result = EuRegulatorsFetcher._fetch_page_html(session, "https://example.com")
        assert result is None

    def test_returns_html_on_200(self) -> None:
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.text = "<html><body>Hello</body></html>"
        session.get.return_value = response

        result = EuRegulatorsFetcher._fetch_page_html(session, "https://example.com")
        assert result == "<html><body>Hello</body></html>"

    def test_returns_none_on_exception(self) -> None:
        import requests as req

        session = MagicMock()
        session.get.side_effect = req.RequestException("timeout")

        result = EuRegulatorsFetcher._fetch_page_html(session, "https://example.com")
        assert result is None
