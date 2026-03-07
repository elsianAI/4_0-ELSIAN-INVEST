"""Tests for elsian.acquire.eu_regulators — offline tests only."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from elsian.acquire.eu_regulators import (
    EuRegulatorsFetcher,
    _TEXT_SUFFIXES,
    _http_get,
    _tilde_media_fallback_url,
)
from elsian.acquire.base import Fetcher
from elsian.models.case import CaseConfig


class TestEuRegulatorsFetcherIsAFetcher:
    def test_is_fetcher(self):
        assert issubclass(EuRegulatorsFetcher, Fetcher)


class TestTextSuffixes:
    def test_expected_suffixes(self):
        assert ".md" in _TEXT_SUFFIXES
        assert ".txt" in _TEXT_SUFFIXES
        assert ".htm" in _TEXT_SUFFIXES
        assert ".html" in _TEXT_SUFFIXES
        assert ".pdf" in _TEXT_SUFFIXES


class TestTildeMediaFallback:
    def test_builds_fallback_url(self):
        url = "https://investors.somero.com/media/Files/S/Somero-IR/documents/2024/annual-report-2024.pdf"
        assert _tilde_media_fallback_url(url) == (
            "https://investors.somero.com/~/media/Files/S/Somero-IR/documents/2024/annual-report-2024.pdf"
        )

    def test_no_fallback_when_already_tilde_media(self):
        url = "https://investors.somero.com/~/media/Files/S/Somero-IR/documents/2024/annual-report-2024.pdf"
        assert _tilde_media_fallback_url(url) is None

    @patch("elsian.acquire.eu_regulators.requests.get")
    def test_http_get_retries_with_tilde_media_variant(
        self, mock_get: MagicMock
    ) -> None:
        resp_404 = MagicMock()
        resp_404.raise_for_status.side_effect = Exception("404")

        from requests import HTTPError
        resp_404.raise_for_status.side_effect = HTTPError("404")

        resp_200 = MagicMock()
        resp_200.raise_for_status.return_value = None
        resp_200.content = b"pdf-bytes"

        mock_get.side_effect = [resp_404, resp_404, resp_404, resp_200]

        content = _http_get(
            "https://investors.somero.com/media/Files/S/Somero-IR/documents/2024/annual-report-2024.pdf",
            retries=2,
        )

        assert content == b"pdf-bytes"
        called_urls = [call.args[0] for call in mock_get.call_args_list]
        assert called_urls[-1] == (
            "https://investors.somero.com/~/media/Files/S/Somero-IR/documents/2024/annual-report-2024.pdf"
        )


class TestEuFetcherWithEmptyCase:
    def test_fetch_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            case = CaseConfig(
                ticker="TEST",
                source_hint="eu",
                case_dir=td,
            )
            fetcher = EuRegulatorsFetcher()
            filings = fetcher.fetch(case)
            assert filings == []

    def test_acquire_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            # Write a case.json so ticker is resolved correctly
            import json
            (Path(td) / "case.json").write_text(json.dumps({"ticker": "TEST"}))

            case = CaseConfig(
                ticker="TEST",
                source_hint="eu",
                case_dir=td,
            )
            fetcher = EuRegulatorsFetcher()
            result = fetcher.acquire(case)
            assert result.ticker == "TEST"
            assert result.source == "eu_manual"
            assert len(result.gaps) > 0  # "No filings found"

    def test_fetch_with_existing_files(self):
        with tempfile.TemporaryDirectory() as td:
            filings_dir = Path(td) / "filings"
            filings_dir.mkdir()
            (filings_dir / "SRC_001_annual.txt").write_text("test content")

            case = CaseConfig(ticker="TEST", source_hint="eu", case_dir=td)
            fetcher = EuRegulatorsFetcher()
            filings = fetcher.fetch(case)
            assert len(filings) == 1
            assert filings[0].primary_doc == "SRC_001_annual.txt"


class TestIrCrawlerFallbackConditions:
    """Test the conditions under which the IR crawler fallback triggers."""

    def test_with_sources_no_crawler(self):
        """filings_sources declared → IR crawler should NOT be called."""
        with tempfile.TemporaryDirectory() as td:
            case_data = {
                "ticker": "TEST",
                "filings_sources": [
                    {"url": "https://example.com/r.pdf", "filename": "r.pdf"},
                ],
                "web_ir": "https://example.com/investors",
            }
            (Path(td) / "case.json").write_text(json.dumps(case_data))

            case = CaseConfig(ticker="TEST", source_hint="eu", case_dir=td)
            fetcher = EuRegulatorsFetcher()

            with patch.object(fetcher, "_acquire_via_ir_crawler", return_value=0) as m:
                with patch("elsian.acquire.eu_regulators._download_sources", return_value=0):
                    fetcher.acquire(case)
            m.assert_not_called()

    def test_without_sources_with_web_ir_calls_crawler(self):
        """No filings_sources, web_ir set → IR crawler should be called."""
        with tempfile.TemporaryDirectory() as td:
            case_data = {
                "ticker": "TEST",
                "web_ir": "https://example.com/investors",
            }
            (Path(td) / "case.json").write_text(json.dumps(case_data))
            (Path(td) / "filings").mkdir()

            case = CaseConfig(ticker="TEST", source_hint="eu", case_dir=td)
            fetcher = EuRegulatorsFetcher()

            with patch.object(fetcher, "_acquire_via_ir_crawler", return_value=0) as m:
                fetcher.acquire(case)
            m.assert_called_once()

    def test_without_sources_without_web_ir_no_crawler(self):
        """No filings_sources, no web_ir → IR crawler should NOT be called."""
        with tempfile.TemporaryDirectory() as td:
            case_data = {"ticker": "TEST"}
            (Path(td) / "case.json").write_text(json.dumps(case_data))
            (Path(td) / "filings").mkdir()

            case = CaseConfig(ticker="TEST", source_hint="eu", case_dir=td)
            fetcher = EuRegulatorsFetcher()

            with patch.object(fetcher, "_acquire_via_ir_crawler", return_value=0) as m:
                fetcher.acquire(case)
            m.assert_not_called()

    def test_without_sources_with_partial_existing_files_calls_crawler(self):
        """Partial filings/ inventory below expected_count should trigger backfill."""
        with tempfile.TemporaryDirectory() as td:
            case_data = {
                "ticker": "TEST",
                "web_ir": "https://example.com/investors",
                "filings_expected_count": 4,
            }
            (Path(td) / "case.json").write_text(json.dumps(case_data))
            filings_dir = Path(td) / "filings"
            filings_dir.mkdir()
            (filings_dir / "annual-2024.pdf").write_text("pdf bytes placeholder")
            (filings_dir / "annual-2024.txt").write_text("converted text")

            case = CaseConfig(ticker="TEST", source_hint="eu", case_dir=td)
            fetcher = EuRegulatorsFetcher()

            with patch.object(fetcher, "_acquire_via_ir_crawler", return_value=0) as m:
                fetcher.acquire(case)
            m.assert_called_once()


class TestIrCrawlerDownloadFiltering:
    @patch("elsian.acquire.eu_regulators.resolve_ir_base_url")
    @patch("elsian.acquire.eu_regulators.build_ir_pages")
    @patch("elsian.acquire.eu_regulators.extract_filing_candidates")
    @patch("elsian.acquire.eu_regulators.discover_ir_subpages")
    @patch("elsian.acquire.eu_regulators.select_fallback_candidates")
    @patch("elsian.acquire.eu_regulators._http_get")
    def test_skips_unsupported_regulatory_story_endpoint(
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
        annual = {
            "url": "https://www.example.com/files/annual-2024.pdf",
            "titulo": "Annual Report 2024",
            "score": 5,
            "tipo_guess": "ANNUAL_REPORT",
            "selection_score": 9.0,
        }
        story = {
            "url": "https://www.example.com/rns/regulatory-story.aspx?newsid=1",
            "titulo": "Regulatory story",
            "score": 5,
            "tipo_guess": "IR_NEWS",
            "selection_score": 8.0,
        }
        mock_extract.return_value = [annual, story]
        mock_select.return_value = [annual, story]
        mock_http_get.return_value = b"%PDF-1.4 fake pdf content"

        with tempfile.TemporaryDirectory() as td:
            filings_dir = Path(td) / "filings"
            filings_dir.mkdir()

            fetcher = EuRegulatorsFetcher()
            with patch.object(
                fetcher, "_fetch_page_html", return_value="<html><body>test</body></html>"
            ):
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
            assert (filings_dir / "annual-2024.pdf").exists()
            assert not any(p.suffix == ".aspx" for p in filings_dir.iterdir())

    @patch("elsian.acquire.eu_regulators.resolve_ir_base_url")
    @patch("elsian.acquire.eu_regulators.build_ir_pages")
    @patch("elsian.acquire.eu_regulators.extract_filing_candidates")
    @patch("elsian.acquire.eu_regulators.discover_ir_subpages")
    @patch("elsian.acquire.eu_regulators.select_fallback_candidates")
    def test_lse_aim_uses_tighter_selection_limits(
        self,
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
        mock_select.return_value = []

        with tempfile.TemporaryDirectory() as td:
            filings_dir = Path(td) / "filings"
            filings_dir.mkdir()
            fetcher = EuRegulatorsFetcher()
            with patch.object(
                fetcher, "_fetch_page_html", return_value="<html><body>test</body></html>"
            ):
                fetcher._acquire_via_ir_crawler(
                    "https://www.example.com/investors",
                    "TEST",
                    filings_dir,
                    exchange="LSE (AIM)",
                )

        _, kwargs = mock_select.call_args
        assert kwargs["max_total"] == 3
        assert kwargs["per_type"]["ANNUAL_REPORT"] == 1
        assert kwargs["per_type"]["INTERIM_REPORT"] == 1
        assert kwargs["per_type"]["REGULATORY_FILING"] == 1
