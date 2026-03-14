"""Tests for ``elsian.acquire.hkex``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from elsian.acquire.hkex import (
    HkexDocument,
    HkexFetcher,
    HkexIssuer,
    _extract_jsonp_payload,
    _lookup_stock,
    _parse_search_documents,
)
from elsian.models.case import CaseConfig


def _make_case(tmp_path: Path, source_hint: str = "hkex_manual") -> CaseConfig:
    """Return a minimal HKEX CaseConfig pointing at ``tmp_path``."""
    return CaseConfig(
        ticker="0327",
        company_name="PAX Global Technology Ltd",
        source_hint=source_hint,
        period_scope="FULL",
        case_dir=str(tmp_path),
    )


def _mock_response(text: str = "", content: bytes = b"") -> MagicMock:
    """Return a response-like mock object."""
    resp = MagicMock()
    resp.text = text
    resp.content = content
    return resp


class TestJsonpParsing:
    def test_extract_jsonp_payload_reads_callback_wrapper(self):
        payload = _extract_jsonp_payload(
            'callback({"more":"1","stockInfo":[{"stockId":56792,"code":"00327","name":"PAX GLOBAL"}]});'
        )
        assert payload["more"] == "1"
        assert payload["stockInfo"][0]["stockId"] == 56792

    def test_extract_jsonp_payload_handles_empty_body(self):
        assert _extract_jsonp_payload("") == {}
        assert _extract_jsonp_payload("\r\n") == {}


class TestSearchParsing:
    def test_parse_search_documents_keeps_supported_financial_titles_only(self):
        html = """
        <div class="title-search-info-footer clearfix">
          <div class="total-records">Total records found: 2 </div>
        </div>
        <div class="title-search-result">
          <table>
            <tbody>
              <tr>
                <td class="release-time">24/08/2023 06:13</td>
                <td>
                  <div class="headline">Circulars - [Other]</div>
                  <div class="doc-link">
                    <a href="/listedco/listconews/sehk/2023/0824/2023082400409.pdf">
                      NOTIFICATION AND REQUEST FORM TO NON-REGISTERED SHAREHOLDER - NOTICE OF PUBLICATION OF INTERIM REPORT 2023
                    </a>
                  </div>
                </td>
              </tr>
              <tr>
                <td class="release-time">24/08/2023 06:05</td>
                <td>
                  <div class="headline">Financial Statements/ESG Information - [Interim/Half-Year Report]</div>
                  <div class="doc-link">
                    <a href="/listedco/listconews/sehk/2023/0824/2023082400379.pdf">
                      INTERIM REPORT 2023
                    </a>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        """
        total_records, documents = _parse_search_documents(html)

        assert total_records == 2
        assert len(documents) == 1
        assert documents[0].title == "INTERIM REPORT 2023"
        assert documents[0].href.endswith("2023082400379.pdf")
        assert documents[0].kind == "IR"
        assert documents[0].year == 2023


class TestLookupFlow:
    def test_lookup_stock_falls_back_from_prefix_to_partial_and_prefers_exact_code(self, tmp_path: Path):
        case = _make_case(tmp_path, source_hint="hkex")
        prefix_empty = _mock_response(text="\r\n")
        partial_match = _mock_response(
            text='callback({"stockInfo":[{"stockId":111,"code":"09999","name":"OTHER"},{"stockId":56792,"code":"00327","name":"PAX GLOBAL"}]});'
        )

        with patch("elsian.acquire.hkex.bounded_get", side_effect=[(prefix_empty, 1), (partial_match, 2)]):
            issuer, retries_total = _lookup_stock(case)

        assert issuer == HkexIssuer(stock_id=56792, code="00327", name="PAX GLOBAL")
        assert retries_total == 3


class TestHkexFetcherCacheAndScan:
    def test_missing_filings_dir_returns_empty_when_live_lookup_fails(self, tmp_path: Path):
        case = _make_case(tmp_path)
        fetcher = HkexFetcher()
        with patch("elsian.acquire.hkex._lookup_stock", return_value=(None, 0)):
            result = fetcher.fetch(case)
        assert result == []

    def test_returns_supported_extensions(self, tmp_path: Path):
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001_AR_FY2024.pdf").touch()
        (filings_dir / "SRC_001_AR_FY2024.txt").touch()
        (filings_dir / "SRC_001_AR_FY2024.clean.md").touch()
        (filings_dir / "SRC_002_IR_H12023.htm").touch()
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

    def test_acquire_uses_cached_manual_corpus_when_dir_not_empty(self, tmp_path: Path):
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001_AR_FY2024.pdf").write_bytes(b"%PDF-1.4 cached")
        (filings_dir / "SRC_001_AR_FY2024.txt").write_text("cached text", encoding="utf-8")
        (filings_dir / "SRC_004_IR_H12025.pdf").write_bytes(b"%PDF-1.4 cached")

        case = _make_case(tmp_path, source_hint="hkex_manual")
        fetcher = HkexFetcher()

        with patch("elsian.acquire.hkex._lookup_stock") as lookup:
            result = fetcher.acquire(case)

        lookup.assert_not_called()
        assert result.cache_hit is True
        assert result.source == "hkex_manual"
        assert result.filings_downloaded == 2
        assert result.coverage["annual"]["downloaded"] == 1
        assert result.coverage["interim"]["downloaded"] == 1


class TestHkexFetcherLiveAcquire:
    def test_acquire_downloads_live_reports_and_generates_txt(self, tmp_path: Path):
        case = _make_case(tmp_path, source_hint="hkex")
        fetcher = HkexFetcher()
        issuer = HkexIssuer(stock_id=56792, code="00327", name="PAX GLOBAL")
        documents = [
            HkexDocument("ANNUAL REPORT 2024", "/annual-2024.pdf", "Annual", "16/04/2025 06:16", 2024, "AR"),
            HkexDocument("ANNUAL REPORT 2023", "/annual-2023.pdf", "Annual", "18/04/2024 06:46", 2023, "AR"),
            HkexDocument("ANNUAL REPORT 2022", "/annual-2022.pdf", "Annual", "18/04/2023 06:44", 2022, "AR"),
            HkexDocument("INTERIM REPORT 2025", "/interim-2025.pdf", "Interim", "28/08/2025 06:07", 2025, "IR"),
            HkexDocument("INTERIM REPORT 2024", "/interim-2024.pdf", "Interim", "29/08/2024 06:05", 2024, "IR"),
            HkexDocument("INTERIM REPORT 2023", "/interim-2023.pdf", "Interim", "24/08/2023 06:05", 2023, "IR"),
        ]
        fake_pdf = b"%PDF-1.4\n" + (b"0" * 256)

        with (
            patch("elsian.acquire.hkex._lookup_stock", return_value=(issuer, 1)),
            patch(
                "elsian.acquire.hkex._discover_documents",
                return_value=(documents, {"coverage": {"search": {"total_records_found": 638}}, "gaps": []}),
            ),
            patch("elsian.acquire.hkex.bounded_get", return_value=(_mock_response(content=fake_pdf), 0)),
            patch("elsian.acquire.hkex.extract_pdf_text_from_file", return_value="converted text"),
            patch("elsian.acquire.hkex.time.sleep"),
        ):
            result = fetcher.acquire(case)

        filings_dir = tmp_path / "filings"
        expected_ids = [
            "SRC_001_AR_FY2024",
            "SRC_002_AR_FY2023",
            "SRC_003_AR_FY2022",
            "SRC_004_IR_H12025",
            "SRC_005_IR_H12024",
            "SRC_006_IR_H12023",
        ]
        for source_id in expected_ids:
            assert (filings_dir / f"{source_id}.pdf").exists()
            assert (filings_dir / f"{source_id}.txt").exists()

        assert result.source == "hkex"
        assert result.filings_downloaded == 6
        assert result.filings_failed == 0
        assert result.filings_coverage_pct == 100.0
        assert result.gaps == []
        assert result.coverage["selected_source_ids"] == expected_ids
        assert result.retries_total == 1

    def test_acquire_reports_lookup_failure(self, tmp_path: Path):
        case = _make_case(tmp_path, source_hint="hkex")
        fetcher = HkexFetcher()

        with patch("elsian.acquire.hkex._lookup_stock", return_value=(None, 2)):
            result = fetcher.acquire(case)

        assert result.source == "hkex"
        assert result.filings_downloaded == 0
        assert result.retries_total == 2
        assert result.gaps == ["HKEX stock lookup failed for 0327"]
