"""Tests for elsian.acquire.transcripts — transcript finder (no network calls)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from elsian.acquire.transcripts import (
    TranscriptFinder,
    TranscriptResult,
    TranscriptSource,
    _build_target_aliases,
    _build_transcript_text,
    _classify_presentation_source_type,
    _clean_ws,
    _extract_company_from_title,
    _extract_transcript_periods,
    _is_low_financial_density,
    _is_navigation_like_source,
    _issuer_match_decision,
    _normalize_entity_name,
    _parse_next_data,
    normalize_period,
)
from elsian.models.case import CaseConfig


# ═══════════════════════════════════════════════════════════════════════
# 1. _normalize_entity_name
# ═══════════════════════════════════════════════════════════════════════


class TestNormalizeEntityName:
    def test_strips_inc(self) -> None:
        assert _normalize_entity_name("Acme Corp Inc.") == "acme"

    def test_strips_corporation(self) -> None:
        assert _normalize_entity_name("Travelzoo Corporation") == "travelzoo"

    def test_strips_ltd(self) -> None:
        assert _normalize_entity_name("Rio Tinto Limited") == "rio tinto"

    def test_strips_sa(self) -> None:
        assert _normalize_entity_name("Teleperformance SA") == "teleperformance"

    def test_strips_plc(self) -> None:
        assert _normalize_entity_name("Barclays PLC") == "barclays"

    def test_strips_brackets_and_parens(self) -> None:
        # Both [NYSE] and (Global) are stripped by the regex
        assert _normalize_entity_name("Acme [NYSE] (Global)") == "acme"

    def test_empty_input(self) -> None:
        assert _normalize_entity_name("") == ""

    def test_none_input(self) -> None:
        assert _normalize_entity_name(None) == ""

    def test_preserves_meaningful_tokens(self) -> None:
        assert _normalize_entity_name("NVIDIA Corporation") == "nvidia"


# ═══════════════════════════════════════════════════════════════════════
# 2. _extract_company_from_title
# ═══════════════════════════════════════════════════════════════════════


class TestExtractCompanyFromTitle:
    def test_earnings_call_pattern(self) -> None:
        result = _extract_company_from_title("Travelzoo Inc. - Earnings Call Transcript")
        assert len(result) >= 1
        assert "Travelzoo Inc." in result

    def test_ticker_q_pattern(self) -> None:
        result = _extract_company_from_title("NVIDIA Corp (NVDA) Q4 2024 Earnings")
        assert len(result) >= 1

    def test_q_year_earnings_pattern(self) -> None:
        result = _extract_company_from_title("Apple Inc Q3 2024 Earnings Call")
        assert len(result) >= 1

    def test_dash_separator(self) -> None:
        result = _extract_company_from_title("Tesla Inc - Q4 2024 Results")
        assert any("Tesla" in r for r in result)

    def test_empty_title(self) -> None:
        assert _extract_company_from_title("") == []

    def test_none_title(self) -> None:
        assert _extract_company_from_title(None) == []


# ═══════════════════════════════════════════════════════════════════════
# 3. _build_target_aliases
# ═══════════════════════════════════════════════════════════════════════


class TestBuildTargetAliases:
    def test_strong_alias(self) -> None:
        aliases, quality = _build_target_aliases("TZOO", "Travelzoo Inc")
        assert quality == "STRONG"
        assert len(aliases) >= 1
        assert "travelzoo" in aliases[0]

    def test_weak_when_no_empresa(self) -> None:
        aliases, quality = _build_target_aliases("TZOO", "")
        assert quality == "WEAK"
        assert len(aliases) == 0

    def test_weak_when_only_ticker(self) -> None:
        aliases, quality = _build_target_aliases("TZOO", "TZOO")
        assert quality == "WEAK"

    def test_strong_multi_word(self) -> None:
        aliases, quality = _build_target_aliases("CROX", "Crocs Inc")
        assert quality == "STRONG"


# ═══════════════════════════════════════════════════════════════════════
# 4. _issuer_match_decision
# ═══════════════════════════════════════════════════════════════════════


class TestIssuerMatchDecision:
    def test_match_exact(self) -> None:
        is_match, score = _issuer_match_decision(
            ["travelzoo"], ["Travelzoo Inc"], "TZOO"
        )
        assert is_match is True
        assert score >= 0.45

    def test_match_similar(self) -> None:
        is_match, score = _issuer_match_decision(
            ["nvidia"], ["NVIDIA Corporation"], "NVDA"
        )
        assert is_match is True
        assert score > 0.4

    def test_mismatch_different_company(self) -> None:
        is_match, score = _issuer_match_decision(
            ["travelzoo"], ["Microsoft Corporation"], "TZOO"
        )
        assert is_match is False

    def test_no_target_aliases(self) -> None:
        is_match, score = _issuer_match_decision([], ["SomeCompany"], "TZOO")
        assert is_match is False
        assert score == 0.0

    def test_no_issuer_candidates(self) -> None:
        is_match, score = _issuer_match_decision(["travelzoo"], [], "TZOO")
        assert is_match is False
        assert score == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 5. _parse_next_data
# ═══════════════════════════════════════════════════════════════════════


class TestParseNextData:
    def test_valid_next_data(self) -> None:
        html = (
            '<html><head></head><body>'
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"pageProps":{"ticker":"TZOO","companyName":"Travelzoo"}}}'
            '</script></body></html>'
        )
        result = _parse_next_data(html)
        assert result is not None
        assert result["props"]["pageProps"]["ticker"] == "TZOO"

    def test_missing_next_data(self) -> None:
        html = "<html><body><p>No data here</p></body></html>"
        assert _parse_next_data(html) is None

    def test_invalid_json(self) -> None:
        html = (
            '<html><body>'
            '<script id="__NEXT_DATA__">{not valid json}</script>'
            '</body></html>'
        )
        assert _parse_next_data(html) is None


# ═══════════════════════════════════════════════════════════════════════
# 6. _build_transcript_text
# ═══════════════════════════════════════════════════════════════════════


class TestBuildTranscriptText:
    def test_basic_structure(self) -> None:
        page_props = {
            "companyName": "Travelzoo",
            "displayPeriod": "Q4 2024",
            "title": "Travelzoo Q4 2024 Earnings Call",
            "publishedAt": "2025-02-15",
            "executiveSummary": ["Revenue grew 10% year over year."],
            "transcript": {
                "transcript": [
                    {
                        "name": "John CEO",
                        "session": "prepared remarks",
                        "speech": ["We had a great quarter.", "Revenue was strong."],
                    }
                ]
            },
        }
        text = _build_transcript_text(page_props)
        assert "Travelzoo Q4 2024 Earnings Call" in text
        assert "Company: Travelzoo" in text
        assert "EXECUTIVE SUMMARY" in text
        assert "Revenue grew 10%" in text
        assert "FULL TRANSCRIPT" in text
        assert "[John CEO]" in text
        assert "We had a great quarter." in text

    def test_no_summary(self) -> None:
        page_props = {
            "companyName": "Test",
            "transcript": {"transcript": []},
        }
        text = _build_transcript_text(page_props)
        assert "EXECUTIVE SUMMARY" not in text
        assert "FULL TRANSCRIPT" in text

    def test_empty_props(self) -> None:
        text = _build_transcript_text({})
        assert "UNKNOWN" in text
        assert "FULL TRANSCRIPT" in text


# ═══════════════════════════════════════════════════════════════════════
# 7. _extract_transcript_periods
# ═══════════════════════════════════════════════════════════════════════


class TestExtractTranscriptPeriods:
    def test_finds_periods(self) -> None:
        html = """
        <a href="/app/research/companies/TZOO/documents/transcripts/q4-2024">Q4 2024</a>
        <a href="/app/research/companies/TZOO/documents/transcripts/q3-2024">Q3 2024</a>
        <a href="/app/research/companies/TZOO/documents/transcripts/q2-2024">Q2 2024</a>
        """
        periods = _extract_transcript_periods(html, "TZOO")
        assert len(periods) == 3
        assert "q4-2024" in periods
        assert "q3-2024" in periods

    def test_no_periods(self) -> None:
        html = "<html><body>No transcript links</body></html>"
        assert _extract_transcript_periods(html, "TZOO") == []

    def test_case_insensitive_ticker(self) -> None:
        html = '<a href="/app/research/companies/tzoo/documents/transcripts/q1-2024">Q1</a>'
        periods = _extract_transcript_periods(html, "TZOO")
        assert len(periods) == 1


# ═══════════════════════════════════════════════════════════════════════
# 8. normalize_period
# ═══════════════════════════════════════════════════════════════════════


class TestNormalizePeriod:
    @pytest.mark.parametrize("raw,expected", [
        ("Q4-2024", "Q4-2024"),
        ("q4-2024", "Q4-2024"),
        ("Q42024", "Q4-2024"),
        ("4Q2024", "Q4-2024"),
        ("FY2024", "FY2024"),
        ("fy-2024", "FY2024"),
        ("Q1-FY2024", "Q1-2024"),
        ("Q1-24", "Q1-2024"),
        ("1Q24", "Q1-2024"),
        (None, "UNKNOWN"),
        ("", "UNKNOWN"),
    ])
    def test_normalization(self, raw: str | None, expected: str) -> None:
        assert normalize_period(raw) == expected


# ═══════════════════════════════════════════════════════════════════════
# 9. _classify_presentation_source_type
# ═══════════════════════════════════════════════════════════════════════


class TestClassifyPresentationSourceType:
    def test_annual_report(self) -> None:
        assert _classify_presentation_source_type(
            "Annual Report 2024", "https://example.com/reports/annual-2024.pdf"
        ) == "ANNUAL_REPORT"

    def test_urd(self) -> None:
        assert _classify_presentation_source_type(
            "Universal Registration Document 2024", "https://example.com/urd-2024.pdf"
        ) == "ANNUAL_REPORT"

    def test_investor_presentation(self) -> None:
        assert _classify_presentation_source_type(
            "Investor Day Presentation", "https://example.com/deck.pdf"
        ) == "INVESTOR_PRESENTATION"

    def test_generic_results(self) -> None:
        assert _classify_presentation_source_type(
            "Q4 Results Deck", "https://example.com/q4-results.pdf"
        ) == "INVESTOR_PRESENTATION"


# ═══════════════════════════════════════════════════════════════════════
# 10. _is_navigation_like_source
# ═══════════════════════════════════════════════════════════════════════


class TestIsNavigationLikeSource:
    def test_pdf_never_navigation(self) -> None:
        assert _is_navigation_like_source(
            "Annual Report", "Annual Report 2024",
            "https://example.com/report.pdf",
        ) is False

    def test_navigation_page_detected(self) -> None:
        text = (
            "Home Search Menu Investor Relations "
            "Corporate Governance Cookie Policy "
            "Latest News Announcements Publications "
            "Financials Overview"
        )
        assert _is_navigation_like_source(
            "Investor Relations", text,
            "https://example.com/investor-relations",
        ) is True

    def test_document_page_not_navigation(self) -> None:
        text = (
            "Revenue was $1,234,567 in Q4 2024. "
            "EBITDA grew 15% to $456,789. Net income increased to $234,567. "
            "EPS of $1.23 exceeded estimates."
        )
        assert _is_navigation_like_source(
            "Q4 Results", text,
            "https://example.com/q4-results",
        ) is False


# ═══════════════════════════════════════════════════════════════════════
# 11. _is_low_financial_density
# ═══════════════════════════════════════════════════════════════════════


class TestIsLowFinancialDensity:
    def test_financial_text(self) -> None:
        text = "Revenue increased to $1,234,567. Net income was $456,789. EBITDA margin improved."
        assert _is_low_financial_density(text) is False

    def test_non_financial_text(self) -> None:
        text = "Welcome to our corporate website. Learn about our team and culture."
        assert _is_low_financial_density(text) is True

    def test_empty_text(self) -> None:
        assert _is_low_financial_density("") is True

    def test_numbers_only(self) -> None:
        text = "The price is $1,234,567 and 45.6% discount applies here."
        # Has numbers but no financial keywords
        assert _is_low_financial_density(text) is True


# ═══════════════════════════════════════════════════════════════════════
# 12. TranscriptSource.to_dict / TranscriptResult.to_dict
# ═══════════════════════════════════════════════════════════════════════


class TestSerialization:
    def test_transcript_source_to_dict(self) -> None:
        src = TranscriptSource(
            source_id="SRC_TRS_001",
            tipo="EARNINGS_TRANSCRIPT",
            period="Q4-2024",
            url="https://fintool.com/TZOO/q4-2024",
            issuer_match=True,
            issuer_match_score=0.8567,
            content_hash="abc123",
            title="TZOO Q4 2024 Earnings Call",
            date="2025-02-15",
            text_chars=12345,
        )
        d = src.to_dict()
        assert d["source_id"] == "SRC_TRS_001"
        assert d["tipo"] == "EARNINGS_TRANSCRIPT"
        assert d["period"] == "Q4-2024"
        assert d["issuer_match"] is True
        assert d["issuer_match_score"] == 0.857  # rounded to 3 dp
        assert d["text_chars"] == 12345

    def test_transcript_result_to_dict(self) -> None:
        result = TranscriptResult(
            ticker="TZOO",
            sources=[
                TranscriptSource(
                    source_id="SRC_TRS_001",
                    tipo="EARNINGS_TRANSCRIPT",
                    period="Q4-2024",
                    url="https://example.com/q4",
                ),
            ],
            discarded=[{"url": "https://bad.com", "reason": "mismatch"}],
            missing=["No presentations found"],
        )
        d = result.to_dict()
        assert d["ticker"] == "TZOO"
        assert len(d["sources"]) == 1
        assert d["sources"][0]["source_id"] == "SRC_TRS_001"
        assert len(d["discarded"]) == 1
        assert len(d["missing"]) == 1

    def test_empty_result_to_dict(self) -> None:
        result = TranscriptResult(ticker="TEST")
        d = result.to_dict()
        assert d["ticker"] == "TEST"
        assert d["sources"] == []
        assert d["discarded"] == []
        assert d["missing"] == []


# ═══════════════════════════════════════════════════════════════════════
# 13. TranscriptFinder.find() — E2E with mocked HTTP
# ═══════════════════════════════════════════════════════════════════════


class TestTranscriptFinderE2E:
    """Full integration test with all HTTP mocked."""

    def _make_fintool_index_html(self, ticker: str, periods: list[str]) -> str:
        links = "\n".join(
            f'<a href="/app/research/companies/{ticker}/documents/transcripts/{p}">{p}</a>'
            for p in periods
        )
        return f"<html><body>{links}</body></html>"

    def _make_fintool_transcript_html(
        self, ticker: str, company: str, period: str
    ) -> str:
        next_data = {
            "props": {
                "pageProps": {
                    "ticker": ticker,
                    "companyName": company,
                    "displayPeriod": period,
                    "title": f"{company} - Earnings Call Transcript",
                    "publishedAt": "February 15, 2025",
                    "executiveSummary": ["Revenue grew 15%."],
                    "transcript": {
                        "transcript": [
                            {
                                "name": "CEO",
                                "session": "prepared remarks",
                                "speech": ["Great quarter."],
                            }
                        ]
                    },
                }
            }
        }
        return (
            f'<html><body>'
            f'<script id="__NEXT_DATA__" type="application/json">'
            f'{json.dumps(next_data)}'
            f'</script></body></html>'
        )

    @patch("elsian.acquire.transcripts._request_text")
    @patch("elsian.acquire.transcripts.resolve_ir_base_url", return_value=None)
    def test_find_us_ticker_with_transcripts(
        self, mock_resolve: MagicMock, mock_request: MagicMock
    ) -> None:
        """US ticker: should find Fintool transcripts."""
        ticker = "TZOO"
        company = "Travelzoo"

        def side_effect(session, url):
            if "documents/transcripts" in url and "q4-2024" not in url and "q3-2024" not in url:
                return self._make_fintool_index_html(ticker, ["q4-2024", "q3-2024"])
            if "q4-2024" in url:
                return self._make_fintool_transcript_html(ticker, company, "Q4-2024")
            if "q3-2024" in url:
                return self._make_fintool_transcript_html(ticker, company, "Q3-2024")
            return "<html></html>"

        mock_request.side_effect = side_effect

        case = CaseConfig(ticker=ticker, source_hint="sec", case_dir="/tmp/fake")
        finder = TranscriptFinder()

        with patch.object(finder, "_load_case_config", return_value={
            "ticker": ticker,
            "company_name": company,
            "country": "US",
        }):
            result = finder.find(case, empresa=company)

        assert result.ticker == ticker
        assert len(result.sources) == 2
        assert all(s.tipo == "EARNINGS_TRANSCRIPT" for s in result.sources)
        assert all(s.issuer_match for s in result.sources)

    @patch("elsian.acquire.transcripts._request_text")
    @patch("elsian.acquire.transcripts.resolve_ir_base_url", return_value=None)
    def test_find_non_us_skips_fintool(
        self, mock_resolve: MagicMock, mock_request: MagicMock
    ) -> None:
        """Non-US ticker: should skip Fintool transcripts."""
        case = CaseConfig(ticker="TEP", source_hint="eu", case_dir="/tmp/fake")
        finder = TranscriptFinder()

        with patch.object(finder, "_load_case_config", return_value={
            "ticker": "TEP",
            "exchange": "EPA",
            "country": "FR",
        }):
            result = finder.find(case)

        # No Fintool calls for non-US
        assert all(s.tipo != "EARNINGS_TRANSCRIPT" for s in result.sources)

    @patch("elsian.acquire.transcripts._request_text")
    @patch("elsian.acquire.transcripts.resolve_ir_base_url", return_value=None)
    def test_find_issuer_mismatch_discards(
        self, mock_resolve: MagicMock, mock_request: MagicMock
    ) -> None:
        """Transcript with wrong company name is discarded."""
        ticker = "TZOO"

        def side_effect(session, url):
            if "documents/transcripts" in url and "q4-2024" not in url:
                return self._make_fintool_index_html(ticker, ["q4-2024"])
            if "q4-2024" in url:
                # Wrong company name
                return self._make_fintool_transcript_html(
                    ticker, "Completely Different Company", "Q4-2024"
                )
            return "<html></html>"

        mock_request.side_effect = side_effect

        case = CaseConfig(ticker=ticker, source_hint="sec", case_dir="/tmp/fake")
        finder = TranscriptFinder()

        with patch.object(finder, "_load_case_config", return_value={
            "ticker": ticker,
            "company_name": "Travelzoo",
            "country": "US",
        }):
            result = finder.find(case, empresa="Travelzoo")

        assert len(result.sources) == 0
        assert len(result.discarded) >= 1
        assert result.discarded[0]["reason"] == "issuer_mismatch"

    @patch("elsian.acquire.transcripts._request_text")
    @patch("elsian.acquire.transcripts.resolve_ir_base_url", return_value="https://ir.example.com")
    @patch("elsian.acquire.transcripts.build_ir_pages", return_value=["https://ir.example.com/presentations"])
    def test_find_with_ir_presentations(
        self,
        mock_build: MagicMock,
        mock_resolve: MagicMock,
        mock_request: MagicMock,
    ) -> None:
        """Finds IR presentations when web_ir is set."""
        ir_html = """
        <html><body>
        <div>
            <a href="https://ir.example.com/annual-report-2024.pdf">
                Annual Report 2024 - Investor Presentation Q4 results
            </a>
        </div>
        </body></html>
        """
        mock_request.return_value = ir_html

        case = CaseConfig(ticker="TEP", source_hint="eu", case_dir="/tmp/fake")
        finder = TranscriptFinder()

        with patch.object(finder, "_load_case_config", return_value={
            "ticker": "TEP",
            "web_ir": "https://ir.example.com",
            "exchange": "EPA",
            "country": "FR",
        }):
            result = finder.find(case)

        # Should have at least one presentation
        pres = [s for s in result.sources if s.tipo in ("INVESTOR_PRESENTATION", "ANNUAL_REPORT")]
        assert len(pres) >= 1


# ═══════════════════════════════════════════════════════════════════════
# 14. Additional edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_clean_ws(self) -> None:
        assert _clean_ws("  hello   world  ") == "hello world"
        assert _clean_ws("") == ""
        assert _clean_ws(None) == ""

    def test_normalize_entity_handles_special_chars(self) -> None:
        assert _normalize_entity_name("O'Reilly Holdings, Inc.") == "o reilly"

    def test_issuer_match_substring_bonus(self) -> None:
        """When one name is a substring of the other, score gets bonus."""
        is_match, score = _issuer_match_decision(
            ["acme technologies global"], ["Acme Technologies"], "ACME"
        )
        assert is_match is True
        assert score >= 0.45

    def test_transcript_source_defaults(self) -> None:
        src = TranscriptSource(
            source_id="SRC_TRS_001",
            tipo="EARNINGS_TRANSCRIPT",
            period=None,
            url="https://example.com",
        )
        assert src.local_path is None
        assert src.issuer_match is False
        assert src.content_hash is None
        assert src.text_chars == 0

    def test_transcript_result_defaults(self) -> None:
        result = TranscriptResult(ticker="TEST")
        assert result.sources == []
        assert result.discarded == []
        assert result.missing == []

    def test_weak_identity_discards_all(self) -> None:
        """With no company name, all transcripts should be discarded."""
        aliases, quality = _build_target_aliases("X", "")
        assert quality == "WEAK"
        # Weak quality means find() will discard all transcripts
