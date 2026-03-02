"""Tests for elsian.acquire.asx — offline logic and edge cases."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

from elsian.acquire import asx
from elsian.acquire.asx import AsxFetcher
from elsian.models.case import CaseConfig


class TestFindFilingsInMonth:
    def test_scans_from_real_month_end_and_respects_max_scan_days(self, monkeypatch):
        scanned: list[dt.date] = []

        def fake_scan_day(_ticker: str, d: dt.date):
            scanned.append(d)
            return []

        monkeypatch.setattr(asx, "_scan_day", fake_scan_day)
        monkeypatch.setattr(asx.time, "sleep", lambda _seconds: None)

        items, day_types = asx._find_filings_in_month("KAR", 2025, 1)

        assert items == []
        assert day_types == set()
        assert scanned[0] == dt.date(2025, 1, 31)
        assert len(scanned) == asx._MAX_SCAN_DAYS
        assert scanned[-1] == dt.date(2025, 1, 31 - (asx._MAX_SCAN_DAYS - 1))

    def test_returns_types_for_first_financial_day(self, monkeypatch):
        def fake_scan_day(_ticker: str, d: dt.date):
            if d.day == 30:
                return [{"header": "Investor Presentation"}]
            if d.day == 29:
                return [
                    {"header": "FY25 results announcement"},
                    {"header": "Annual Report 2025"},
                ]
            return []

        monkeypatch.setattr(asx, "_scan_day", fake_scan_day)
        monkeypatch.setattr(asx.time, "sleep", lambda _seconds: None)

        items, day_types = asx._find_filings_in_month("KAR", 2025, 1)

        assert len(items) == 2
        assert day_types == {"annual", "results"}


class TestSearchAllWindows:
    def test_does_not_count_results_only_as_annual(self, monkeypatch):
        class FakeDate(dt.date):
            @classmethod
            def today(cls) -> FakeDate:
                return cls(2026, 3, 15)

        calls: list[tuple[int, int]] = []

        def fake_find(_ticker: str, year: int, month: int):
            calls.append((year, month))
            if month == 2:
                return (
                    [{
                        "id": f"R-{year}",
                        "header": f"FY{str(year)[-2:]} results announcement",
                        "document_release_date": f"{year}-02-20",
                    }],
                    {"results"},
                )
            if month == 3:
                return (
                    [{
                        "id": f"A-{year}",
                        "header": f"Annual Report {year}",
                        "document_release_date": f"{year}-03-20",
                    }],
                    {"annual"},
                )
            return [], set()

        monkeypatch.setattr(asx.dt, "date", FakeDate)
        monkeypatch.setattr(asx, "_find_filings_in_month", fake_find)

        items = asx._search_all_windows(
            "KAR", years_back=1, fy_end_month=12, halfyear_target=0,
        )

        assert calls == [(2026, 2), (2026, 3), (2025, 2), (2025, 3)]
        assert {item["id"] for item in items} == {"R-2026", "A-2026", "R-2025", "A-2025"}


class TestAcquireBehavior:
    def test_cache_counts_logical_filings(self):
        with tempfile.TemporaryDirectory() as td:
            filings_dir = Path(td) / "filings"
            filings_dir.mkdir()
            (filings_dir / "SRC_001_annual_FY2025.pdf").write_bytes(b"x")
            (filings_dir / "SRC_001_annual_FY2025.txt").write_text("x", encoding="utf-8")
            (filings_dir / "SRC_002_results_FY2025.pdf").write_bytes(b"x")

            case = CaseConfig(ticker="KAR", source_hint="asx", case_dir=td)
            result = AsxFetcher().acquire(case)

            assert result.filings_downloaded == 2
            assert result.source == "asx"

    def test_annual_only_uses_zero_halfyear_target(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            case = CaseConfig(
                ticker="KAR",
                source_hint="asx",
                case_dir=td,
                period_scope="ANNUAL_ONLY",
            )

            captured: dict[str, int] = {}

            def fake_search(_ticker: str, years_back: int, fy_end_month: int, halfyear_target: int):
                captured["halfyear_target"] = halfyear_target
                return [
                    {
                        "id": "A1",
                        "header": "Annual Report 2025",
                        "document_release_date": "2026-02-20",
                        "url": "https://example.com/a1.pdf",
                    },
                    {
                        "id": "H1",
                        "header": "Half Year Report 2025",
                        "document_release_date": "2025-08-20",
                        "url": "https://example.com/h1.pdf",
                    },
                    {
                        "id": "R1",
                        "header": "FY25 results announcement",
                        "document_release_date": "2026-02-21",
                        "url": "https://example.com/r1.pdf",
                    },
                ]

            def fake_download(_url: str, dest: Path) -> bool:
                dest.write_bytes(b"%PDF-1.4 fake")
                return True

            counter = {"n": 0}

            def fake_extract(_pdf_bytes: bytes) -> str:
                counter["n"] += 1
                return f"text-{counter['n']}"

            monkeypatch.setattr(asx, "_search_all_windows", fake_search)
            monkeypatch.setattr(asx, "_download_pdf", fake_download)
            monkeypatch.setattr(asx, "extract_pdf_text", fake_extract)
            monkeypatch.setattr(asx.time, "sleep", lambda _seconds: None)

            result = AsxFetcher().acquire(case)

            assert captured["halfyear_target"] == 0
            assert result.coverage["halfyear"]["target"] == 0
            assert result.coverage["halfyear"]["downloaded"] == 0
            assert result.filings_downloaded == 2  # annual + results
