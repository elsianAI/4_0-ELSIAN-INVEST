"""Tests for elsian.acquire.eu_regulators — offline tests only."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from elsian.acquire.eu_regulators import EuRegulatorsFetcher, _TEXT_SUFFIXES
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