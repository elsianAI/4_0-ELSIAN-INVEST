"""Integration tests for ``elsian curate`` — BL-031.

Validates the end-to-end curate workflow:
1. E2E with TZOO (SEC 10-K, iXBRL embedded in .htm)
2. E2E with TEP (EU PDF-only — no .htm files, skeleton output)
3. Coverage of TZOO draft vs expected.json ground truth (≥80%)
4. Sanity checks with artificial draft data (no disk I/O)

Tests that parse real filings are marked ``@pytest.mark.slow``.
Run the fast subset with:  pytest tests/integration/test_curate.py -m "not slow"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Generator

import pytest

from elsian.cli import CASES_DIR, cmd_curate
from elsian.extract.ixbrl import run_sanity_checks

# ---------------------------------------------------------------------------
# Module-scoped fixtures — cmd_curate runs once per session per ticker
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tzoo_draft() -> Generator[dict, None, None]:
    """Execute cmd_curate for TZOO; yield the parsed draft; clean up on exit.

    scope=module → cmd_curate runs once for all TZOO tests in this file.
    Teardown always removes the generated file, even if tests fail.
    """
    draft_path = CASES_DIR / "TZOO" / "expected_draft.json"
    # Remove any leftover from a previous run
    if draft_path.exists():
        draft_path.unlink()

    cmd_curate(argparse.Namespace(ticker="TZOO"))

    if not draft_path.exists():
        pytest.fail("cmd_curate did not create expected_draft.json for TZOO")

    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    yield draft

    if draft_path.exists():
        draft_path.unlink()


@pytest.fixture(scope="module")
def tep_draft() -> Generator[dict, None, None]:
    """Execute cmd_curate for TEP (no .htm files); yield skeleton; clean up."""
    draft_path = CASES_DIR / "TEP" / "expected_draft.json"
    if draft_path.exists():
        draft_path.unlink()

    cmd_curate(argparse.Namespace(ticker="TEP"))

    if not draft_path.exists():
        pytest.fail("cmd_curate did not create expected_draft.json for TEP")

    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    yield draft

    if draft_path.exists():
        draft_path.unlink()


# ---------------------------------------------------------------------------
# E2E — TZOO (iXBRL in 10-K .htm files)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCurateTZOO:
    """E2E tests for cmd_curate with a real SEC iXBRL ticker (TZOO)."""

    def test_draft_file_created_on_disk(self, tzoo_draft: dict) -> None:
        """cmd_curate writes expected_draft.json to cases/TZOO/."""
        assert (CASES_DIR / "TZOO" / "expected_draft.json").exists()

    def test_draft_has_at_least_one_period(self, tzoo_draft: dict) -> None:
        """Draft contains at least one period extracted from the filings."""
        assert len(tzoo_draft.get("periods", {})) >= 1

    def test_at_least_one_period_has_five_canonical_fields(self, tzoo_draft: dict) -> None:
        """At least one period exposes ≥5 canonical field entries."""
        periods = tzoo_draft.get("periods", {})
        assert any(
            len(pdata.get("fields", {})) >= 5 for pdata in periods.values()
        ), "No period in TZOO draft has ≥5 canonical fields — concept_map may be broken"

    def test_all_fields_carry_concept_and_filing_provenance(self, tzoo_draft: dict) -> None:
        """Every field entry must have ``_concept`` and ``_filing`` provenance keys."""
        for plabel, pdata in tzoo_draft.get("periods", {}).items():
            for fname, fdata in pdata.get("fields", {}).items():
                assert "_concept" in fdata, f"{plabel}/{fname}: missing _concept"
                assert "_filing" in fdata, f"{plabel}/{fname}: missing _filing"

    def test_generated_by_marker_is_set(self, tzoo_draft: dict) -> None:
        """Draft carries the correct _generated_by marker."""
        assert tzoo_draft.get("_generated_by") == "elsian curate"

    def test_draft_has_required_top_level_structure(self, tzoo_draft: dict) -> None:
        """Draft contains version, ticker, currency, scale, periods."""
        for key in ("version", "ticker", "currency", "scale", "periods"):
            assert key in tzoo_draft, f"Draft missing top-level key: {key}"


# ---------------------------------------------------------------------------
# E2E — TEP (PDF-only, no iXBRL → skeleton output)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCurateTEP:
    """E2E tests for cmd_curate when no .htm files are present (TEP)."""

    def test_skeleton_file_created_on_disk(self, tep_draft: dict) -> None:
        """cmd_curate creates expected_draft.json even without .htm files."""
        assert (CASES_DIR / "TEP" / "expected_draft.json").exists()

    def test_skeleton_generated_by_marker(self, tep_draft: dict) -> None:
        """Skeleton carries the correct _generated_by marker."""
        assert tep_draft.get("_generated_by") == "elsian curate (skeleton)"

    def test_skeleton_has_empty_periods(self, tep_draft: dict) -> None:
        """Skeleton periods dict is empty — no iXBRL data available."""
        assert tep_draft.get("periods") == {}

    def test_skeleton_has_required_top_level_keys(self, tep_draft: dict) -> None:
        """Skeleton contains version, ticker, currency, scale, periods."""
        for key in ("version", "ticker", "currency", "scale", "periods"):
            assert key in tep_draft, f"Skeleton missing key: {key}"


# ---------------------------------------------------------------------------
# Coverage: TZOO draft vs expected.json ground truth
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestTZOODraftCoverage:
    """Validate that the curate draft covers ≥80% of expected.json FY fields.

    This test is the regression guard for the iXBRL parser and concept_map.
    If someone breaks the parser or removes a mapping, the coverage drops
    below 80% and this test fails immediately.
    """

    def test_all_fy_periods_present_in_draft(self, tzoo_draft: dict) -> None:
        """Every FY period from expected.json must appear in the draft."""
        expected = json.loads(
            (CASES_DIR / "TZOO" / "expected.json").read_text(encoding="utf-8")
        )
        fy_periods = [p for p in expected["periods"] if p.startswith("FY")]
        draft_periods = set(tzoo_draft.get("periods", {}).keys())
        missing = [p for p in fy_periods if p not in draft_periods]
        assert not missing, (
            f"FY periods missing from draft: {missing}. "
            "Check that the corresponding .htm filings exist in cases/TZOO/filings/."
        )

    def test_fy_field_coverage_at_least_90pct(self, tzoo_draft: dict) -> None:
        """≥90% of canonical fields per FY period must appear in the draft.

        Computed across all FY periods in expected.json:
            coverage = total matched fields / total expected fields
        """
        expected = json.loads(
            (CASES_DIR / "TZOO" / "expected.json").read_text(encoding="utf-8")
        )
        fy_periods = [p for p in expected["periods"] if p.startswith("FY")]
        assert len(fy_periods) > 0, "No FY periods in TZOO expected.json — sanity failure"

        total_expected_fields = 0
        total_matched = 0

        for period in fy_periods:
            exp_fields = set(expected["periods"][period].get("fields", {}).keys())
            draft_fields = set(
                tzoo_draft.get("periods", {}).get(period, {}).get("fields", {}).keys()
            )
            total_expected_fields += len(exp_fields)
            total_matched += len(exp_fields & draft_fields)

        assert total_expected_fields > 0
        coverage = total_matched / total_expected_fields
        assert coverage >= 0.90, (
            f"iXBRL parser field coverage is {coverage:.1%} "
            f"({total_matched}/{total_expected_fields} fields across "
            f"{len(fy_periods)} FY periods from expected.json). "
            "Expected ≥90%. The parser or ixbrl_concept_map.json may be broken."
        )


# ---------------------------------------------------------------------------
# Sanity checks (in-memory, no disk I/O — not marked as slow)
# ---------------------------------------------------------------------------


class TestSanityChecks:
    """Tests for run_sanity_checks() with handcrafted draft data."""

    def test_balance_sheet_inconsistency_triggers_warning(self) -> None:
        """A ≠ L + E beyond ±5% tolerance must produce ≥1 warning."""
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "total_assets":      {"value": 100},
                        "total_liabilities": {"value": 60},
                        "total_equity":      {"value": 10},  # L+E=70 ≠ 100 → dev=43%
                    }
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert len(warnings) >= 1
        assert any("A≠L+E" in w for w in warnings), (
            f"Expected a balance-sheet warning containing 'A≠L+E'. Got: {warnings}"
        )

    def test_balanced_sheet_produces_no_inequality_warning(self) -> None:
        """A = L + E (exact) must not produce a balance-sheet warning."""
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "total_assets":      {"value": 100},
                        "total_liabilities": {"value": 60},
                        "total_equity":      {"value": 40},  # L+E=100 = A ✓
                    }
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert not any("A≠L+E" in w for w in warnings)

    def test_negative_revenue_triggers_warning(self) -> None:
        """ingresos ≤ 0 must trigger a warning."""
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {"ingresos": {"value": -1_000}}
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert any("ingresos" in w for w in warnings)

    def test_opposing_ni_eps_signs_triggers_warning(self) -> None:
        """net_income > 0 but eps_basic < 0 must flag opposite sign warning."""
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "net_income": {"value": 1_000},
                        "eps_basic":  {"value": -1.50},
                    }
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert any("opposite signs" in w for w in warnings)

    def test_empty_periods_produces_no_warnings(self) -> None:
        """A draft with no periods must return an empty warnings list."""
        assert run_sanity_checks({"periods": {}}) == []

    def test_well_formed_draft_no_warnings(self) -> None:
        """A draft with internally consistent data must pass all sanity checks."""
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "ingresos":          {"value": 1_000_000},
                        "net_income":        {"value": 50_000},
                        "eps_basic":         {"value": 1.25},
                        "total_assets":      {"value": 500_000},
                        "total_liabilities": {"value": 300_000},
                        "total_equity":      {"value": 200_000},
                    }
                }
            }
        }
        assert run_sanity_checks(draft) == []
