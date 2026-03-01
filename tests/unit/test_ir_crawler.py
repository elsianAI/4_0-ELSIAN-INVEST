"""Tests for elsian.acquire.ir_crawler — IR website crawling utilities."""

import pytest

from elsian.acquire.ir_crawler import (
    _clean_embedded_pdf_url,
    _extract_date_from_html_document,
    _extract_embedded_pdf_candidates,
    _extract_embedded_title,
    _local_event_registration_penalty,
    _prefer_new_candidate,
    _resolve_local_candidate_date,
    build_ir_pages,
    build_ir_url_candidates,
    derive_ir_roots,
    discover_ir_subpages,
    extract_filing_candidates,
    normalize_web_ir,
    parse_date_loose,
    parse_year_hint,
    select_fallback_candidates,
)


# ── normalize_web_ir ──────────────────────────────────────────────────

class TestNormalizeWebIr:
    def test_adds_https(self) -> None:
        assert normalize_web_ir("example.com/investors") == "https://example.com/investors"

    def test_strips_trailing_slash(self) -> None:
        assert normalize_web_ir("https://example.com/investors/") == "https://example.com/investors"

    def test_preserves_existing_scheme(self) -> None:
        assert normalize_web_ir("http://example.com") == "http://example.com"

    def test_empty_returns_none(self) -> None:
        assert normalize_web_ir("") is None
        assert normalize_web_ir(None) is None


# ── build_ir_url_candidates ───────────────────────────────────────────

class TestBuildIrUrlCandidates:
    def test_generates_variants(self) -> None:
        candidates = build_ir_url_candidates("https://www.somero.com/investors")
        assert "https://www.somero.com/investors" in candidates
        assert "https://investors.somero.com" in candidates
        assert "https://www.somero.com/investor-relations" in candidates

    def test_no_duplicates(self) -> None:
        candidates = build_ir_url_candidates("https://www.example.com/investors")
        assert len(candidates) == len(set(candidates))

    def test_already_investor_relations(self) -> None:
        candidates = build_ir_url_candidates("https://www.example.com/investor-relations")
        # Original URL should be first
        assert candidates[0] == "https://www.example.com/investor-relations"
        # No exact duplicates
        assert len(candidates) == len(set(candidates))


# ── derive_ir_roots ───────────────────────────────────────────────────

class TestDeriveIrRoots:
    def test_basic(self) -> None:
        roots = derive_ir_roots("https://www.example.com/investors")
        assert "https://www.example.com/investors" in roots
        assert "https://www.example.com" in roots

    def test_locale_prefix(self) -> None:
        roots = derive_ir_roots("https://www.example.com/en-us/investors")
        assert any("en-us/investors" in r for r in roots)

    def test_homepage_tail_trimmed(self) -> None:
        roots = derive_ir_roots("https://www.example.com/investors/investors-homepage")
        # The homepage tail should be trimmed; /investors should appear
        assert any(r.endswith("/investors") for r in roots)

    def test_no_duplicates(self) -> None:
        roots = derive_ir_roots("https://www.example.com/investors")
        assert len(roots) == len(set(roots))


# ── build_ir_pages ────────────────────────────────────────────────────

class TestBuildIrPages:
    def test_generates_pages(self) -> None:
        pages = build_ir_pages("https://www.example.com/investors")
        assert len(pages) > 5
        assert "https://www.example.com/investors" in pages

    def test_includes_suffixes(self) -> None:
        pages = build_ir_pages("https://www.example.com/investors")
        assert any("annual-reports" in p for p in pages)
        assert any("financial-results" in p for p in pages)

    def test_empty(self) -> None:
        assert build_ir_pages("") == []
        assert build_ir_pages(None) == []

    def test_no_duplicates(self) -> None:
        pages = build_ir_pages("https://www.example.com/investors")
        assert len(pages) == len(set(pages))


# ── discover_ir_subpages ─────────────────────────────────────────────

_SAMPLE_HTML = """
<html><body>
  <a href="/investors/annual-reports">Annual Reports</a>
  <a href="/investors/financial-results">Financial Results</a>
  <a href="/careers">Careers</a>
  <a href="https://other-domain.com/page">External</a>
  <a href="/investors/report.pdf">PDF Report</a>
</body></html>
"""


class TestDiscoverIrSubpages:
    def test_finds_subpages(self) -> None:
        subpages = discover_ir_subpages(
            _SAMPLE_HTML, "https://www.example.com/investors"
        )
        assert any("annual-reports" in s for s in subpages)
        assert any("financial-results" in s for s in subpages)

    def test_excludes_external(self) -> None:
        subpages = discover_ir_subpages(
            _SAMPLE_HTML, "https://www.example.com/investors"
        )
        assert not any("other-domain.com" in s for s in subpages)

    def test_excludes_careers(self) -> None:
        subpages = discover_ir_subpages(
            _SAMPLE_HTML, "https://www.example.com/investors"
        )
        assert not any("careers" in s for s in subpages)

    def test_excludes_pdf(self) -> None:
        subpages = discover_ir_subpages(
            _SAMPLE_HTML, "https://www.example.com/investors"
        )
        assert not any(s.endswith(".pdf") for s in subpages)


# ── extract_filing_candidates ─────────────────────────────────────────

_IR_HTML = """
<html><body>
  <div>
    <a href="/docs/annual-report-2024.pdf">Annual Report 2024</a>
    <a href="/docs/interim-report-h1-2024.pdf">H1 2024 Interim Report</a>
    <a href="/docs/results-q3-2024.pdf">Q3 2024 Results</a>
    <a href="/contact">Contact Us</a>
  </div>
</body></html>
"""


class TestExtractFilingCandidates:
    def test_finds_candidates(self) -> None:
        candidates = extract_filing_candidates(
            _IR_HTML, "https://www.example.com/investors"
        )
        assert len(candidates) >= 2

    def test_annual_report_classified(self) -> None:
        candidates = extract_filing_candidates(
            _IR_HTML, "https://www.example.com/investors"
        )
        annuals = [c for c in candidates if c["tipo_guess"] == "ANNUAL_REPORT"]
        assert len(annuals) >= 1

    def test_sorted_by_score(self) -> None:
        candidates = extract_filing_candidates(
            _IR_HTML, "https://www.example.com/investors"
        )
        for i in range(len(candidates) - 1):
            assert candidates[i]["selection_score"] >= candidates[i + 1]["selection_score"]

    def test_fallback_page_date_when_candidate_has_no_date(self) -> None:
        html = """
        <html>
          <head><meta property="article:published_time" content="2024-07-31"></head>
          <body><a href="/docs/annual-report.pdf">Annual Report</a></body>
        </html>
        """
        candidates = extract_filing_candidates(html, "https://www.example.com/investors")
        assert len(candidates) >= 1
        cand = next(c for c in candidates if "annual-report.pdf" in c["url"])
        assert cand["fecha_publicacion"] == "2024-07-31"
        assert cand["fecha_source"] == "page_html_meta"
        assert cand["fecha_publicacion_estimated"] is True

    def test_do_not_override_context_date_with_page_date(self) -> None:
        html = """
        <html>
          <head><meta property="article:published_time" content="2024-07-31"></head>
          <body>
            <a href="/docs/annual-report.pdf">Annual Report March 15, 2024</a>
          </body>
        </html>
        """
        candidates = extract_filing_candidates(html, "https://www.example.com/investors")
        cand = next(c for c in candidates if "annual-report.pdf" in c["url"])
        assert cand["fecha_publicacion"] == "2024-03-15"
        assert cand["fecha_source"] == "context"


# ── select_fallback_candidates ────────────────────────────────────────

class TestSelectFallbackCandidates:
    def test_respects_per_type_limit(self) -> None:
        candidates = [
            {"tipo_guess": "ANNUAL_REPORT", "selection_score": 10.0},
            {"tipo_guess": "ANNUAL_REPORT", "selection_score": 9.0},
            {"tipo_guess": "ANNUAL_REPORT", "selection_score": 8.0},
            {"tipo_guess": "ANNUAL_REPORT", "selection_score": 7.0},
            {"tipo_guess": "ANNUAL_REPORT", "selection_score": 6.0},
        ]
        selected = select_fallback_candidates(candidates, per_type={"ANNUAL_REPORT": 3, "_default": 2})
        assert len(selected) == 3

    def test_respects_max_total(self) -> None:
        candidates = [
            {"tipo_guess": "ANNUAL_REPORT", "selection_score": 10.0},
            {"tipo_guess": "INTERIM_REPORT", "selection_score": 9.0},
            {"tipo_guess": "REGULATORY_FILING", "selection_score": 8.0},
        ]
        selected = select_fallback_candidates(candidates, max_total=2)
        assert len(selected) == 2

    def test_empty(self) -> None:
        assert select_fallback_candidates([]) == []

    def test_tie_break_by_fecha_when_score_equal(self) -> None:
        candidates = [
            {
                "tipo_guess": "ANNUAL_REPORT",
                "selection_score": 10.0,
                "fecha_publicacion": "2024-03-15",
            },
            {
                "tipo_guess": "ANNUAL_REPORT",
                "selection_score": 10.0,
                "fecha_publicacion": "2024-10-01",
            },
        ]
        selected = select_fallback_candidates(
            candidates,
            max_total=2,
            per_type={"ANNUAL_REPORT": 5, "_default": 2},
        )
        assert selected[0]["fecha_publicacion"] == "2024-10-01"


# ── parse_date_loose ──────────────────────────────────────────────────

class TestParseDateLoose:
    def test_iso_date(self) -> None:
        assert parse_date_loose("2024-03-15") == "2024-03-15"

    def test_slash_date(self) -> None:
        assert parse_date_loose("2024/06/01") == "2024-06-01"

    def test_compact_date(self) -> None:
        assert parse_date_loose("report_20240315.pdf") == "2024-03-15"

    def test_text_date_us(self) -> None:
        assert parse_date_loose("March 15, 2024") == "2024-03-15"

    def test_text_date_eu(self) -> None:
        assert parse_date_loose("15 March 2024") == "2024-03-15"

    def test_abbreviated_month(self) -> None:
        assert parse_date_loose("Sep 1, 2023") == "2023-09-01"

    def test_empty_returns_none(self) -> None:
        assert parse_date_loose("") is None
        assert parse_date_loose(None) is None

    def test_no_date_returns_none(self) -> None:
        assert parse_date_loose("just some text") is None


# ── parse_year_hint ───────────────────────────────────────────────────

class TestParseYearHint:
    def test_annual_report(self) -> None:
        assert parse_year_hint("Annual Report 2024") == 2024

    def test_fy_prefix(self) -> None:
        assert parse_year_hint("FY2023 results") == 2023

    def test_no_keyword_returns_none(self) -> None:
        assert parse_year_hint("some text 2024") is None

    def test_empty_returns_none(self) -> None:
        assert parse_year_hint("") is None

    def test_picks_max_year(self) -> None:
        assert parse_year_hint("Annual Report 2023 2024") == 2024


# ── _resolve_local_candidate_date ─────────────────────────────────────

class TestResolveLocalCandidateDate:
    def test_date_from_anchor_text(self) -> None:
        date, source, estimated = _resolve_local_candidate_date(
            "Annual Report March 15, 2024", "", "https://example.com/report.pdf"
        )
        assert date == "2024-03-15"
        assert source == "context"
        assert estimated is False

    def test_date_from_url(self) -> None:
        date, source, estimated = _resolve_local_candidate_date(
            "Report", "", "https://example.com/reports/2024-06-30/report.pdf"
        )
        assert date == "2024-06-30"
        assert source == "url"
        assert estimated is True

    def test_year_hint_fallback(self) -> None:
        date, source, estimated = _resolve_local_candidate_date(
            "Annual Report 2024", "", "https://example.com/report.pdf"
        )
        assert date == "2024-12-31"
        assert source == "title_year"
        assert estimated is True

    def test_no_date(self) -> None:
        date, source, estimated = _resolve_local_candidate_date(
            "Some doc", "", "https://example.com/doc.pdf"
        )
        assert date is None
        assert source == "unknown"


# ── _extract_date_from_html_document ──────────────────────────────────

class TestExtractDateFromHtmlDocument:
    def test_meta_published_time(self) -> None:
        html = '<html><head><meta property="article:published_time" content="2024-03-15"></head></html>'
        date, source = _extract_date_from_html_document(html, "https://example.com")
        assert date == "2024-03-15"
        assert source == "html_meta"

    def test_meta_date_name(self) -> None:
        html = '<html><head><meta name="date" content="2024-06-01"></head></html>'
        date, source = _extract_date_from_html_document(html, "https://example.com")
        assert date == "2024-06-01"
        assert source == "html_meta"

    def test_time_tag(self) -> None:
        html = '<html><body><time datetime="2024-09-01">Sep 1, 2024</time></body></html>'
        date, source = _extract_date_from_html_document(html, "https://example.com")
        assert date == "2024-09-01"
        assert source == "html_time_tag"

    def test_title_date(self) -> None:
        html = "<html><head><title>Results March 15, 2024</title></head></html>"
        date, source = _extract_date_from_html_document(html, "https://example.com")
        assert date == "2024-03-15"
        assert source == "html_title"

    def test_url_fallback(self) -> None:
        html = "<html><head><title>Report</title></head></html>"
        date, source = _extract_date_from_html_document(
            html, "https://example.com/2024-01-15/report"
        )
        assert date == "2024-01-15"
        assert source == "url"

    def test_no_date(self) -> None:
        html = "<html><body>No date here</body></html>"
        date, source = _extract_date_from_html_document(html, "https://example.com")
        assert date is None
        assert source == "unknown"


# ── _local_event_registration_penalty ─────────────────────────────────

class TestLocalEventRegistrationPenalty:
    def test_strong_hint_engagestream(self) -> None:
        penalty = _local_event_registration_penalty("engagestream link", "https://example.com")
        assert penalty <= -3.0

    def test_webcast_penalty(self) -> None:
        penalty = _local_event_registration_penalty("webcast invitation", "https://example.com")
        assert penalty <= -3.0

    def test_event_only(self) -> None:
        penalty = _local_event_registration_penalty("some event today", "https://example.com")
        assert penalty == -1.0

    def test_no_penalty(self) -> None:
        penalty = _local_event_registration_penalty("annual report 2024", "https://example.com/report.pdf")
        assert penalty == 0.0

    def test_registration_in_url(self) -> None:
        penalty = _local_event_registration_penalty("report", "https://example.com/registration/2024")
        assert penalty <= -3.0


# ── _clean_embedded_pdf_url ───────────────────────────────────────────

class TestCleanEmbeddedPdfUrl:
    def test_basic_cleanup(self) -> None:
        assert _clean_embedded_pdf_url('"https://example.com/report.pdf"') == "https://example.com/report.pdf"

    def test_html_entity(self) -> None:
        url = _clean_embedded_pdf_url("https://example.com/report&amp;v=1.pdf")
        assert "&amp;" not in url

    def test_escaped_slashes(self) -> None:
        url = _clean_embedded_pdf_url("https:\\/\\/example.com\\/report.pdf")
        assert url == "https://example.com/report.pdf"

    def test_unicode_escape(self) -> None:
        url = _clean_embedded_pdf_url("https:\\u002f\\u002fexample.com\\u002freport.pdf")
        assert url == "https://example.com/report.pdf"

    def test_protocol_relative(self) -> None:
        url = _clean_embedded_pdf_url("//cdn.example.com/report.pdf")
        assert url == "https://cdn.example.com/report.pdf"

    def test_empty(self) -> None:
        assert _clean_embedded_pdf_url("") == ""


# ── _extract_embedded_title ───────────────────────────────────────────

class TestExtractEmbeddedTitle:
    def test_gtm_elem_text(self) -> None:
        ctx = 'data-gtm-elem-text="Annual Report 2024 Full Year"'
        assert _extract_embedded_title(ctx, "https://example.com/report.pdf") == "Annual Report 2024 Full Year"

    def test_name_value_json(self) -> None:
        ctx = '"name": {"Value": "Integrated Annual Report 2024"}'
        assert _extract_embedded_title(ctx, "https://example.com/report.pdf") == "Integrated Annual Report 2024"

    def test_title_json(self) -> None:
        ctx = '"title": "Q1 2024 Financial Results"'
        assert _extract_embedded_title(ctx, "https://example.com/report.pdf") == "Q1 2024 Financial Results"

    def test_fallback_to_filename(self) -> None:
        ctx = "some random context without patterns"
        result = _extract_embedded_title(ctx, "https://example.com/Annual_Report_2024.pdf")
        assert "Annual_Report_2024" in result


# ── _prefer_new_candidate ─────────────────────────────────────────────

class TestPreferNewCandidate:
    def test_higher_score_wins(self) -> None:
        prev = {"score": 3, "selection_score": 5.0}
        new = {"score": 5, "selection_score": 7.0}
        assert _prefer_new_candidate(prev, new) is True

    def test_lower_score_loses(self) -> None:
        prev = {"score": 5, "selection_score": 7.0}
        new = {"score": 3, "selection_score": 5.0}
        assert _prefer_new_candidate(prev, new) is False

    def test_date_protection(self) -> None:
        prev = {"score": 3, "fecha_publicacion": "2024-03-15", "selection_score": 5.0}
        new = {"score": 4, "selection_score": 6.0}  # no date, score delta = 1
        assert _prefer_new_candidate(prev, new) is False

    def test_date_protection_overridden_by_large_delta(self) -> None:
        prev = {"score": 3, "fecha_publicacion": "2024-03-15", "selection_score": 5.0}
        new = {"score": 5, "selection_score": 7.0}  # no date, but delta = 2
        assert _prefer_new_candidate(prev, new) is True

    def test_tied_score_prefers_date(self) -> None:
        prev = {"score": 3, "selection_score": 5.0}
        new = {"score": 3, "fecha_publicacion": "2024-03-15", "selection_score": 5.0}
        assert _prefer_new_candidate(prev, new) is True

    def test_tied_score_keeps_dated(self) -> None:
        prev = {"score": 3, "fecha_publicacion": "2024-03-15", "selection_score": 5.0}
        new = {"score": 3, "selection_score": 5.0}
        assert _prefer_new_candidate(prev, new) is False

    def test_tied_with_both_dates_uses_selection_score(self) -> None:
        prev = {"score": 3, "fecha_publicacion": "2024-03-15", "selection_score": 5.0}
        new = {"score": 3, "fecha_publicacion": "2024-06-01", "selection_score": 6.0}
        assert _prefer_new_candidate(prev, new) is True


# ── _extract_embedded_pdf_candidates ──────────────────────────────────

class TestExtractEmbeddedPdfCandidates:
    def test_finds_absolute_pdf_urls(self) -> None:
        html = '''
        <div>
            <script>var data = {"url": "https://cdn.example.com/annual-report-2024.pdf", "title": "Annual Report 2024"}</script>
        </div>
        '''
        cands = _extract_embedded_pdf_candidates(html, "https://example.com", "EPA")
        assert len(cands) >= 1
        assert any("annual-report-2024.pdf" in c["url"] for c in cands)

    def test_filters_negative_hints(self) -> None:
        html = '<a href="https://example.com/privacy-policy.pdf">Privacy Policy</a>'
        cands = _extract_embedded_pdf_candidates(html, "https://example.com", None)
        assert all("privacy" not in c["url"].lower() for c in cands)

    def test_requires_positive_hints(self) -> None:
        html = '<div>Link to https://example.com/random-document.pdf in context</div>'
        cands = _extract_embedded_pdf_candidates(html, "https://example.com", None)
        # No positive hints → should not be included
        assert len(cands) == 0

    def test_candidates_have_date_fields(self) -> None:
        html = '''
        <div>Published on March 15, 2024:
            See https://cdn.example.com/annual-results-2024.pdf for details
        </div>
        '''
        cands = _extract_embedded_pdf_candidates(html, "https://example.com", None)
        for c in cands:
            assert "fecha_publicacion" in c
            assert "fecha_source" in c
            assert "fecha_publicacion_estimated" in c
            assert c.get("discovered_via") == "embedded_pdf"

    def test_embedded_fallback_uses_page_date(self) -> None:
        html = """
        <div>
          "title": "Annual Report"
          https://cdn.example.com/reports/annual-report.pdf
        </div>
        """
        cands = _extract_embedded_pdf_candidates(
            html,
            "https://example.com/investors",
            "EPA",
            page_date="2024-06-30",
            page_date_source="html_meta",
        )
        assert len(cands) >= 1
        cand = next(c for c in cands if "annual-report.pdf" in c["url"])
        assert cand["fecha_publicacion"] == "2024-06-30"
        assert cand["fecha_source"] == "page_html_meta"


# ── extract_filing_candidates integration ─────────────────────────────

class TestExtractFilingCandidatesIntegration:
    def test_candidates_have_date_fields(self) -> None:
        html = '''
        <html><body>
        <a href="/reports/annual-report-2024.pdf">Annual Report March 15, 2024</a>
        </body></html>
        '''
        cands = extract_filing_candidates(html, "https://example.com")
        assert len(cands) >= 1
        for c in cands:
            assert "fecha_publicacion" in c
            assert "fecha_source" in c
            assert "fecha_publicacion_estimated" in c

    def test_event_penalty_applied(self) -> None:
        html = '''
        <html><body>
        <a href="/reports/annual-report-2024.pdf">Annual Report 2024 results filing</a>
        <a href="https://engagestream.com/webcast/2024">Annual Webcast Registration results filing</a>
        </body></html>
        '''
        cands = extract_filing_candidates(html, "https://example.com")
        # The annual report should rank higher than the webcast
        if len(cands) >= 1:
            assert "annual-report" in cands[0]["url"]
