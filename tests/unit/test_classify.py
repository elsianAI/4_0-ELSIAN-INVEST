"""Tests for elsian.acquire.classify — filing classification and quality."""

import pytest

from elsian.acquire.classify import (
    classify_annual_extractability,
    classify_filing_type,
    financial_signal_hits,
)


# ── classify_filing_type ──────────────────────────────────────────────

class TestClassifyFilingType:
    def test_annual_report(self) -> None:
        assert classify_filing_type("Annual Report 2024", "https://x.com/ar.pdf", "") == "ANNUAL_REPORT"

    def test_urd(self) -> None:
        assert classify_filing_type("Universal Registration Document", "https://x.com/urd.pdf", "") == "ANNUAL_REPORT"

    def test_urd_french(self) -> None:
        assert classify_filing_type("Document d'enregistrement universel", "https://x.com/", "") == "ANNUAL_REPORT"

    def test_interim_report(self) -> None:
        assert classify_filing_type("H1 2024 Interim Report", "https://x.com/h1.pdf", "") == "INTERIM_REPORT"

    def test_half_year(self) -> None:
        assert classify_filing_type("Half year results", "https://x.com/", "") == "INTERIM_REPORT"

    def test_press_release_with_results(self) -> None:
        result = classify_filing_type("Press Release - Q1 Results", "https://x.com/pr.pdf", "financial results")
        assert result == "REGULATORY_FILING"

    def test_press_release_generic(self) -> None:
        assert classify_filing_type("Press Release", "https://x.com/pr.pdf", "new product launch") == "IR_NEWS"

    def test_rns(self) -> None:
        assert classify_filing_type("RNS Announcement", "https://x.com/rns", "") == "IR_NEWS"

    def test_regulatory_news(self) -> None:
        assert classify_filing_type("Regulatory news", "https://x.com/", "") == "IR_NEWS"

    def test_results_generic(self) -> None:
        assert classify_filing_type("Full year results 2024", "https://x.com/", "") == "REGULATORY_FILING"

    def test_media_youtube(self) -> None:
        assert classify_filing_type("Earnings call", "https://youtube.com/watch?v=xyz", "") == "OTHER"

    def test_media_extension(self) -> None:
        assert classify_filing_type("Webcast", "https://x.com/video.mp4", "") == "OTHER"

    def test_other(self) -> None:
        assert classify_filing_type("Contact Us", "https://x.com/contact", "phone email") == "OTHER"

    def test_rapport_annuel(self) -> None:
        assert classify_filing_type("Rapport annuel 2024", "https://x.com/ra.pdf", "") == "ANNUAL_REPORT"


# ── financial_signal_hits ─────────────────────────────────────────────

class TestFinancialSignalHits:
    def test_finds_signals(self) -> None:
        text = "Total revenue was $5M. Net income $1M. Total assets $20M."
        count, hits = financial_signal_hits(text)
        assert count >= 3
        assert "revenue" in hits
        assert "income" in hits
        assert "assets" in hits

    def test_empty(self) -> None:
        count, hits = financial_signal_hits("")
        assert count == 0
        assert hits == []

    def test_no_signals(self) -> None:
        count, hits = financial_signal_hits("The quick brown fox jumps over the lazy dog.")
        assert count == 0


# ── classify_annual_extractability ────────────────────────────────────

class TestClassifyAnnualExtractability:
    def test_non_annual_passthrough(self) -> None:
        status, reason, meta = classify_annual_extractability(
            tipo="INTERIM_REPORT",
            extraction_status="OK",
            extraction_reason="",
            text_chars=500,
            text_sample="tiny",
        )
        assert status == "OK"
        assert meta == {}

    def test_already_failed_passthrough(self) -> None:
        status, reason, meta = classify_annual_extractability(
            tipo="ANNUAL_REPORT",
            extraction_status="FAILED",
            extraction_reason="download error",
            text_chars=100,
            text_sample="",
        )
        assert status == "FAILED"

    def test_low_text_downgrade(self) -> None:
        status, reason, meta = classify_annual_extractability(
            tipo="ANNUAL_REPORT",
            extraction_status="OK",
            extraction_reason="",
            text_chars=200,
            text_sample="tiny text",
        )
        assert status == "NON_EXTRACTABLE_LOW_TEXT_ANNUAL"
        assert meta["rejected_low_quality"] is True
        assert meta["reject_reason"] == "LOW_TEXT_ANNUAL"

    def test_low_signal_downgrade(self) -> None:
        status, reason, meta = classify_annual_extractability(
            tipo="10-K",
            extraction_status="OK",
            extraction_reason="",
            text_chars=5000,
            text_sample="A document about corporate governance and board of directors.",
        )
        assert status == "NON_EXTRACTABLE_LOW_SIGNAL_ANNUAL"
        assert meta["rejected_low_quality"] is True

    def test_good_annual_passes(self) -> None:
        sample = "Revenue was $5M. Net income $1M. Total assets $20M. Cash flow from operations. Total equity. EBITDA margin."
        status, reason, meta = classify_annual_extractability(
            tipo="ANNUAL_REPORT",
            extraction_status="OK",
            extraction_reason="",
            text_chars=10000,
            text_sample=sample,
        )
        assert status == "OK"
        assert meta["rejected_low_quality"] is False

    def test_20f_recognized(self) -> None:
        sample = "Revenue $100M. Profit $20M. liabilities $50M."
        status, reason, meta = classify_annual_extractability(
            tipo="20-F",
            extraction_status="OK",
            extraction_reason="",
            text_chars=5000,
            text_sample=sample,
        )
        assert status == "OK"
