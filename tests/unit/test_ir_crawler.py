"""Tests for elsian.acquire.ir_crawler — IR website crawling utilities."""

import pytest

from elsian.acquire.ir_crawler import (
    build_ir_pages,
    build_ir_url_candidates,
    derive_ir_roots,
    discover_ir_subpages,
    extract_filing_candidates,
    normalize_web_ir,
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
