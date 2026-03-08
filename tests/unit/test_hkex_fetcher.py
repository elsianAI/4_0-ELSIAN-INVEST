"""Tests for elsian.acquire.hkex -- offline, no network calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from elsian.acquire.hkex import HkexFetcher
from elsian.models.case import CaseConfig


def _make_case(tmp_path: Path) -> CaseConfig:
    """Return a minimal CaseConfig pointing at tmp_path."""
    return CaseConfig(
        ticker="0327",
        company_name="PAX Global Technology Ltd",
        source_hint="hkex_manual",
        case_dir=str(tmp_path),
    )


class TestHkexFetcherEmptyDir:
    def test_missing_filings_dir_returns_empty(self, tmp_path: Path):
        case = _make_case(tmp_path)
        # no filings/ subdirectory created
        fetcher = HkexFetcher()
        result = fetcher.fetch(case)
        assert result == []

    def test_empty_filings_dir_returns_empty(self, tmp_path: Path):
        (tmp_path / "filings").mkdir()
        case = _make_case(tmp_path)
        fetcher = HkexFetcher()
        result = fetcher.fetch(case)
        assert result == []


class TestHkexFetcherFileScan:
    def test_returns_supported_extensions(self, tmp_path: Path):
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        # create files with various extensions
        (filings_dir / "SRC_001_AR_FY2024.pdf").touch()
        (filings_dir / "SRC_001_AR_FY2024.txt").touch()
        (filings_dir / "SRC_001_AR_FY2024.clean.md").touch()
        (filings_dir / "SRC_002_IR_H12023.htm").touch()
        # this should be excluded
        (filings_dir / "notes.docx").touch()

        case = _make_case(tmp_path)
        fetcher = HkexFetcher()
        result = fetcher.fetch(case)

        names = {f.primary_doc for f in result}
        assert "SRC_001_AR_FY2024.pdf" in names
        assert "SRC_001_AR_FY2024.txt" in names
        assert "SRC_001_AR_FY2024.clean.md" in names
        assert "SRC_002_IR_H12023.htm" in names
        assert "notes.docx" not in names
        assert len(result) == 4

    def test_results_are_sorted(self, tmp_path: Path):
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_003_AR_FY2022.txt").touch()
        (filings_dir / "SRC_001_AR_FY2024.txt").touch()
        (filings_dir / "SRC_002_AR_FY2023.txt").touch()

        case = _make_case(tmp_path)
        fetcher = HkexFetcher()
        result = fetcher.fetch(case)

        docs = [f.primary_doc for f in result]
        assert docs == sorted(docs)

    def test_source_id_is_stem(self, tmp_path: Path):
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_004_IR_H12025.clean.md").touch()

        case = _make_case(tmp_path)
        fetcher = HkexFetcher()
        result = fetcher.fetch(case)

        assert len(result) == 1
        assert result[0].source_id == "SRC_004_IR_H12025.clean"
        assert result[0].local_path.endswith("SRC_004_IR_H12025.clean.md")

    def test_directories_are_ignored(self, tmp_path: Path):
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "subdir.txt").mkdir()  # dir with .txt-like name
        (filings_dir / "SRC_001_AR_FY2024.txt").touch()

        case = _make_case(tmp_path)
        fetcher = HkexFetcher()
        result = fetcher.fetch(case)

        assert len(result) == 1
        assert result[0].primary_doc == "SRC_001_AR_FY2024.txt"
