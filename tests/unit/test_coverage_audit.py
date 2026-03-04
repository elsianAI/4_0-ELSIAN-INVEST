"""Unit tests for elsian.evaluate.coverage_audit (BL-021)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from elsian.evaluate.coverage_audit import (
    THRESHOLDS,
    build_report,
    evaluate_case,
    issuer_class,
    render_markdown,
    _extract_filing_metrics,
    _check_thresholds,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_case(
    tmp_path: Path,
    ticker: str,
    *,
    source_hint: str = "sec",
    country: str = "US",
    cik: str | None = "1234567",
    period_scope: str = "ANNUAL_ONLY",
    manifest: dict | None = None,
) -> Path:
    """Create a minimal case directory with case.json and optional manifest."""
    case_dir = tmp_path / ticker
    case_dir.mkdir()
    case_data = {
        "ticker": ticker,
        "source_hint": source_hint,
        "country": country,
        "currency": "USD",
        "exchange": "NASDAQ",
        "cik": cik,
        "period_scope": period_scope,
    }
    (case_dir / "case.json").write_text(
        json.dumps(case_data), encoding="utf-8"
    )
    if manifest is not None:
        (case_dir / "filings_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
    return case_dir


def _make_manifest(
    total: int = 20,
    annual: int = 5,
    quarterly: int = 10,
    earnings: int = 5,
    failed: int = 0,
) -> dict:
    return {
        "filings_downloaded": total,
        "filings_failed": failed,
        "coverage": {
            "annual":    {"downloaded": annual},
            "quarterly": {"downloaded": quarterly},
            "earnings":  {"downloaded": earnings},
        },
    }


# ---------------------------------------------------------------------------
# Tests: issuer_class
# ---------------------------------------------------------------------------

class TestIssuerClass:
    def test_domestic_us_sec(self):
        assert issuer_class("sec", "US", "1234567") == "Domestic_US"

    def test_domestic_us_sec_edgar(self):
        assert issuer_class("sec_edgar", "US", "1234567") == "Domestic_US"

    def test_domestic_us_no_country(self):
        """SEC filer with no country code → default Domestic_US."""
        assert issuer_class("sec", None, "9999999") == "Domestic_US"

    def test_fpi_adr_non_us_country(self):
        """SEC filer with non-US country → FPI_ADR."""
        assert issuer_class("sec", "IL", "1849396") == "FPI_ADR"

    def test_fpi_adr_cayman(self):
        assert issuer_class("sec", "KY", "1857816") == "FPI_ADR"

    def test_nonus_local_asx(self):
        assert issuer_class("asx", None, None) == "NonUS_Local"

    def test_nonus_local_eu_manual(self):
        assert issuer_class("eu_manual", "FR", None) == "NonUS_Local"

    def test_nonus_local_manual_http(self):
        assert issuer_class("manual_http", "AU", None) == "NonUS_Local"

    def test_nonus_local_unknown_no_cik(self):
        """Unknown source hint with no CIK → NonUS_Local."""
        assert issuer_class("some_local_exchange", "JP", None) == "NonUS_Local"

    def test_nonus_asx_overrides_us_country(self):
        """ASX source hint takes precedence over country code."""
        assert issuer_class("asx", "US", None) == "NonUS_Local"


# ---------------------------------------------------------------------------
# Tests: _extract_filing_metrics
# ---------------------------------------------------------------------------

class TestExtractFilingMetrics:
    def test_none_manifest(self):
        m = _extract_filing_metrics(None)
        assert m == {"total": 0, "annual": 0, "quarterly": 0, "earnings": 0, "failed": 0}

    def test_full_manifest(self):
        manifest = _make_manifest(total=26, annual=6, quarterly=12, earnings=10, failed=2)
        m = _extract_filing_metrics(manifest)
        assert m["total"] == 26
        assert m["annual"] == 6
        assert m["quarterly"] == 12
        assert m["earnings"] == 10
        assert m["failed"] == 2

    def test_empty_coverage(self):
        """Manifest with empty coverage dict should return zeros for sub-fields."""
        manifest = {"filings_downloaded": 6, "filings_failed": 0, "coverage": {}}
        m = _extract_filing_metrics(manifest)
        assert m["total"] == 6
        assert m["annual"] == 0
        assert m["quarterly"] == 0


# ---------------------------------------------------------------------------
# Tests: _check_thresholds
# ---------------------------------------------------------------------------

class TestCheckThresholds:
    def test_domestic_us_pass(self):
        metrics = {"total": 20, "annual": 5, "quarterly": 10, "earnings": 5, "failed": 0}
        assert _check_thresholds("Domestic_US", metrics) == []

    def test_domestic_us_fail_annual(self):
        metrics = {"total": 12, "annual": 2, "quarterly": 5, "earnings": 5, "failed": 0}
        req = _check_thresholds("Domestic_US", metrics)
        assert any("ANNUAL" in r for r in req)

    def test_domestic_us_fail_total(self):
        metrics = {"total": 5, "annual": 4, "quarterly": 0, "earnings": 0, "failed": 0}
        req = _check_thresholds("Domestic_US", metrics)
        assert any("TOTAL" in r for r in req)

    def test_fpi_adr_pass(self):
        metrics = {"total": 10, "annual": 3, "quarterly": 5, "earnings": 2, "failed": 0}
        assert _check_thresholds("FPI_ADR", metrics) == []

    def test_fpi_adr_fail_annual(self):
        metrics = {"total": 8, "annual": 1, "quarterly": 5, "earnings": 2, "failed": 0}
        req = _check_thresholds("FPI_ADR", metrics)
        assert any("ANNUAL" in r for r in req)

    def test_nonus_local_pass(self):
        metrics = {"total": 3, "annual": 0, "quarterly": 0, "earnings": 0, "failed": 0}
        assert _check_thresholds("NonUS_Local", metrics) == []

    def test_nonus_local_fail_total(self):
        metrics = {"total": 0, "annual": 0, "quarterly": 0, "earnings": 0, "failed": 0}
        req = _check_thresholds("NonUS_Local", metrics)
        assert any("TOTAL" in r for r in req)


# ---------------------------------------------------------------------------
# Tests: evaluate_case
# ---------------------------------------------------------------------------

class TestEvaluateCase:
    def test_domestic_us_pass(self, tmp_path):
        """Domestic US ticker with enough filings → PASS."""
        case_dir = _make_case(
            tmp_path, "TZOO", source_hint="sec", country="US", cik="1133311",
            manifest=_make_manifest(total=26, annual=6, quarterly=12, earnings=10),
        )
        result = evaluate_case(case_dir)
        assert result["ticker"] == "TZOO"
        assert result["issuer_class"] == "Domestic_US"
        assert result["status"] == "PASS"
        assert result["required_actions"] == []
        assert result["has_manifest"] is True

    def test_domestic_us_needs_action_low_annual(self, tmp_path):
        """Domestic US with annual < 3 → NEEDS_ACTION."""
        case_dir = _make_case(
            tmp_path, "LOWANNUAL", source_hint="sec", country="US", cik="9999",
            manifest=_make_manifest(total=15, annual=2, quarterly=8, earnings=5),
        )
        result = evaluate_case(case_dir)
        assert result["status"] == "NEEDS_ACTION"
        assert any("ANNUAL" in r for r in result["required_actions"])

    def test_domestic_us_needs_action_low_total(self, tmp_path):
        """Domestic US with total < 10 → NEEDS_ACTION."""
        case_dir = _make_case(
            tmp_path, "LOWTOTAL", source_hint="sec", country="US", cik="9988",
            manifest=_make_manifest(total=5, annual=4, quarterly=1, earnings=0),
        )
        result = evaluate_case(case_dir)
        assert result["status"] == "NEEDS_ACTION"
        assert any("TOTAL" in r for r in result["required_actions"])

    def test_fpi_adr_pass(self, tmp_path):
        """FPI with enough annual + total → PASS."""
        case_dir = _make_case(
            tmp_path, "GCT", source_hint="sec", country="KY", cik="1857816",
            manifest=_make_manifest(total=26, annual=4, quarterly=12, earnings=10),
        )
        result = evaluate_case(case_dir)
        assert result["issuer_class"] == "FPI_ADR"
        assert result["status"] == "PASS"

    def test_fpi_adr_needs_action(self, tmp_path):
        """FPI with annual < 2 → NEEDS_ACTION."""
        case_dir = _make_case(
            tmp_path, "LOWFPI", source_hint="sec", country="IL", cik="1234",
            manifest=_make_manifest(total=8, annual=1, quarterly=4, earnings=3),
        )
        result = evaluate_case(case_dir)
        assert result["issuer_class"] == "FPI_ADR"
        assert result["status"] == "NEEDS_ACTION"

    def test_nonus_local_pass(self, tmp_path):
        """Non-US local with 1+ filings → PASS."""
        case_dir = _make_case(
            tmp_path, "KAR", source_hint="asx", country=None, cik=None,
            manifest=_make_manifest(total=6, annual=0, quarterly=0, earnings=0),
        )
        result = evaluate_case(case_dir)
        assert result["issuer_class"] == "NonUS_Local"
        assert result["status"] == "PASS"

    def test_nonus_local_needs_action_no_manifest(self, tmp_path):
        """Non-US local with no manifest → NEEDS_ACTION."""
        case_dir = _make_case(
            tmp_path, "TEP", source_hint="eu_manual", country="FR", cik=None,
            manifest=None,
        )
        result = evaluate_case(case_dir)
        assert result["issuer_class"] == "NonUS_Local"
        assert result["status"] == "NEEDS_ACTION"
        assert result["has_manifest"] is False

    def test_no_manifest_domestic_needs_action(self, tmp_path):
        """Domestic_US with no manifest → NEEDS_ACTION (0 filings)."""
        case_dir = _make_case(
            tmp_path, "NOMFST", source_hint="sec", country="US", cik="1111",
            manifest=None,
        )
        result = evaluate_case(case_dir)
        assert result["has_manifest"] is False
        assert result["status"] == "NEEDS_ACTION"

    def test_cik_from_manifest_when_missing_in_case(self, tmp_path):
        """If CIK is missing from case.json but present in manifest, use manifest CIK."""
        case_dir = _make_case(
            tmp_path, "CIKTEST", source_hint="sec", country="US", cik=None
        )
        manifest = _make_manifest(total=20, annual=5, quarterly=12, earnings=3)
        manifest["cik"] = "0001133311"
        (case_dir / "filings_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        result = evaluate_case(case_dir)
        assert result["cik"] == "0001133311"
        assert result["issuer_class"] == "Domestic_US"

    def test_ticker_falls_back_to_dir_name(self, tmp_path):
        """If case.json has no 'ticker' key, dir name is used."""
        case_dir = tmp_path / "FALLBACK"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"source_hint": "sec", "country": "US", "cik": "9000"}),
            encoding="utf-8",
        )
        result = evaluate_case(case_dir)
        assert result["ticker"] == "FALLBACK"


# ---------------------------------------------------------------------------
# Tests: build_report
# ---------------------------------------------------------------------------

class TestBuildReport:
    def _setup_cases(self, tmp_path: Path) -> Path:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        _make_case(
            cases_dir, "AAAA", source_hint="sec", country="US", cik="1111",
            manifest=_make_manifest(total=20, annual=5, quarterly=10, earnings=5),
        )
        _make_case(
            cases_dir, "BBBB", source_hint="sec", country="IL", cik="2222",
            manifest=_make_manifest(total=10, annual=3, quarterly=5, earnings=2),
        )
        _make_case(
            cases_dir, "CCCC", source_hint="asx", country=None, cik=None,
            manifest=None,   # No manifest → NEEDS_ACTION
        )
        return cases_dir

    def test_build_report_keys(self, tmp_path):
        """build_report returns required top-level keys."""
        cases_dir = self._setup_cases(tmp_path)
        report = build_report(cases_dir)
        for key in ("version", "generated_at", "cases_dir", "summary", "cases", "pass", "needs_action"):
            assert key in report

    def test_build_report_summary_counts(self, tmp_path):
        """Summary counts match actual case status."""
        cases_dir = self._setup_cases(tmp_path)
        report = build_report(cases_dir)
        s = report["summary"]
        assert s["total_tickers"] == 3
        assert s["pass_count"] == 2
        assert s["needs_action_count"] == 1

    def test_build_report_class_counts(self, tmp_path):
        """Class counts correctly distributed."""
        cases_dir = self._setup_cases(tmp_path)
        report = build_report(cases_dir)
        cc = report["summary"]["class_counts"]
        assert cc["Domestic_US"] == 1
        assert cc["FPI_ADR"] == 1
        assert cc["NonUS_Local"] == 1

    def test_build_report_pass_needs_action_lists(self, tmp_path):
        """pass and needs_action lists contain the right tickers."""
        cases_dir = self._setup_cases(tmp_path)
        report = build_report(cases_dir)
        pass_tickers = {c["ticker"] for c in report["pass"]}
        na_tickers = {c["ticker"] for c in report["needs_action"]}
        assert "AAAA" in pass_tickers
        assert "BBBB" in pass_tickers
        assert "CCCC" in na_tickers

    def test_build_report_empty_cases_dir(self, tmp_path):
        """Empty cases directory → zero tickers."""
        cases_dir = tmp_path / "empty_cases"
        cases_dir.mkdir()
        report = build_report(cases_dir)
        assert report["summary"]["total_tickers"] == 0
        assert report["pass"] == []
        assert report["needs_action"] == []


# ---------------------------------------------------------------------------
# Tests: render_markdown
# ---------------------------------------------------------------------------

class TestRenderMarkdown:
    def _simple_report(self, tmp_path: Path) -> dict:
        cases_dir = tmp_path / "cases"
        cases_dir.mkdir()
        _make_case(
            cases_dir, "PASS1", source_hint="sec", country="US", cik="1111",
            manifest=_make_manifest(total=20, annual=5, quarterly=10, earnings=5),
        )
        _make_case(
            cases_dir, "FAIL1", source_hint="asx", country=None, cik=None,
            manifest=None,
        )
        return build_report(cases_dir)

    def test_render_markdown_has_title(self, tmp_path):
        md = render_markdown(self._simple_report(tmp_path))
        assert "# Coverage Audit Report" in md

    def test_render_markdown_has_needs_action_section(self, tmp_path):
        md = render_markdown(self._simple_report(tmp_path))
        assert "## Needs Action" in md

    def test_render_markdown_has_pass_section(self, tmp_path):
        md = render_markdown(self._simple_report(tmp_path))
        assert "## PASS" in md

    def test_render_markdown_lists_pass_ticker(self, tmp_path):
        md = render_markdown(self._simple_report(tmp_path))
        assert "PASS1" in md

    def test_render_markdown_lists_needs_action_ticker(self, tmp_path):
        md = render_markdown(self._simple_report(tmp_path))
        assert "FAIL1" in md

    def test_render_markdown_contains_class_table(self, tmp_path):
        md = render_markdown(self._simple_report(tmp_path))
        assert "Issuer Class" in md
        assert "Domestic_US" in md
        assert "NonUS_Local" in md

    def test_render_markdown_nonempty(self, tmp_path):
        md = render_markdown(self._simple_report(tmp_path))
        assert len(md) > 100
