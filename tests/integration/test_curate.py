"""Integration tests for ``elsian curate`` — BL-031 / BL-052.

Validates the end-to-end curate workflow:
1. E2E with TZOO (SEC 10-K, iXBRL embedded in .htm)
2. E2E with TEP (EU PDF-only — deterministic PDF/text draft)
3. E2E with KAR (ASX PDF-only — deterministic PDF/text draft)
4. Coverage of TZOO draft vs expected.json ground truth (≥80%)
5. Sanity checks with artificial draft data (no disk I/O)

Tests that parse real filings are marked ``@pytest.mark.slow``.
Run the fast subset with:  pytest tests/integration/test_curate.py -m "not slow"
"""

from __future__ import annotations

import argparse
import json
from typing import Generator

import pytest

from elsian.cli import CASES_DIR, cmd_curate
from elsian.extract.ixbrl import run_sanity_checks


@pytest.fixture(scope="module")
def tzoo_draft() -> Generator[dict, None, None]:
    """Execute cmd_curate for TZOO; yield the parsed draft; clean up on exit."""
    draft_path = CASES_DIR / "TZOO" / "expected_draft.json"
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
    """Execute cmd_curate for TEP (no .htm files); yield deterministic draft; clean up."""
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


@pytest.fixture(scope="module")
def kar_draft() -> Generator[dict, None, None]:
    """Execute cmd_curate for KAR (PDF-only); yield deterministic draft; clean up."""
    draft_path = CASES_DIR / "KAR" / "expected_draft.json"
    if draft_path.exists():
        draft_path.unlink()

    cmd_curate(argparse.Namespace(ticker="KAR"))

    if not draft_path.exists():
        pytest.fail("cmd_curate did not create expected_draft.json for KAR")

    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    yield draft

    if draft_path.exists():
        draft_path.unlink()


@pytest.mark.slow
class TestCurateTZOO:
    """E2E tests for cmd_curate with a real SEC iXBRL ticker (TZOO)."""

    def test_draft_file_created_on_disk(self, tzoo_draft: dict) -> None:
        assert (CASES_DIR / "TZOO" / "expected_draft.json").exists()

    def test_draft_has_at_least_one_period(self, tzoo_draft: dict) -> None:
        assert len(tzoo_draft.get("periods", {})) >= 1

    def test_at_least_one_period_has_five_canonical_fields(self, tzoo_draft: dict) -> None:
        periods = tzoo_draft.get("periods", {})
        assert any(
            len(pdata.get("fields", {})) >= 5 for pdata in periods.values()
        ), "No period in TZOO draft has >=5 canonical fields"

    def test_all_fields_carry_concept_and_filing_provenance(self, tzoo_draft: dict) -> None:
        for plabel, pdata in tzoo_draft.get("periods", {}).items():
            for fname, fdata in pdata.get("fields", {}).items():
                assert "_concept" in fdata, f"{plabel}/{fname}: missing _concept"
                assert "_filing" in fdata, f"{plabel}/{fname}: missing _filing"

    def test_generated_by_marker_is_set(self, tzoo_draft: dict) -> None:
        assert tzoo_draft.get("_generated_by") == "elsian curate"

    def test_draft_has_required_top_level_structure(self, tzoo_draft: dict) -> None:
        for key in ("version", "ticker", "currency", "scale", "periods"):
            assert key in tzoo_draft, f"Draft missing top-level key: {key}"


@pytest.mark.slow
class TestCurateTEP:
    """E2E tests for cmd_curate when no .htm files are present (TEP)."""

    def test_draft_file_created_on_disk(self, tep_draft: dict) -> None:
        assert (CASES_DIR / "TEP" / "expected_draft.json").exists()

    def test_draft_generated_by_marker(self, tep_draft: dict) -> None:
        assert tep_draft.get("_generated_by") == "elsian curate"
        assert tep_draft.get("_source_mode") == "pipeline_non_sec"

    def test_draft_has_material_periods(self, tep_draft: dict) -> None:
        periods = tep_draft.get("periods", {})
        assert len(periods) >= 1
        assert any(len(pdata.get("fields", {})) >= 5 for pdata in periods.values())

    def test_draft_exposes_confidence_and_gaps(self, tep_draft: dict) -> None:
        first_period = next(iter(sorted(tep_draft["periods"])))
        pdata = tep_draft["periods"][first_period]
        assert "_confidence" in pdata
        assert "_gaps" in pdata
        assert isinstance(pdata["_confidence"]["field_counts"], dict)
        assert isinstance(pdata["_confidence"]["non_high_fields"], list)
        assert "missing_canonicals" in pdata["_gaps"]
        assert "missing_count" in pdata["_gaps"]
        assert "skipped_manual_fields" in pdata["_gaps"]

    def test_draft_has_required_top_level_keys(self, tep_draft: dict) -> None:
        for key in (
            "version",
            "ticker",
            "currency",
            "scale",
            "periods",
            "_source_mode",
            "_confidence_summary",
            "_gap_policy",
            "_validation",
            "_comparison_to_expected",
        ):
            assert key in tep_draft, f"Draft missing key: {key}"

    def test_draft_has_material_coverage_vs_expected(self, tep_draft: dict) -> None:
        comparison = tep_draft.get("_comparison_to_expected", {})
        assert comparison.get("coverage_pct", 0) >= 90.0
        assert comparison.get("value_match_pct", 0) >= 90.0


@pytest.mark.slow
class TestCurateKAR:
    """E2E tests for cmd_curate when the case is ASX/PDF-only (KAR)."""

    def test_draft_file_created_on_disk(self, kar_draft: dict) -> None:
        assert (CASES_DIR / "KAR" / "expected_draft.json").exists()

    def test_kar_draft_is_non_empty(self, kar_draft: dict) -> None:
        periods = kar_draft.get("periods", {})
        assert len(periods) >= 1
        assert any(len(pdata.get("fields", {})) >= 10 for pdata in periods.values())

    def test_kar_draft_exposes_confidence_and_gaps(self, kar_draft: dict) -> None:
        first_period = next(iter(sorted(kar_draft["periods"])))
        pdata = kar_draft["periods"][first_period]
        assert "_confidence" in pdata
        assert "_gaps" in pdata
        assert isinstance(pdata["_gaps"].get("missing_canonicals"), list)
        assert isinstance(pdata["_confidence"]["field_counts"], dict)

    def test_kar_draft_has_material_coverage_vs_expected(self, kar_draft: dict) -> None:
        comparison = kar_draft.get("_comparison_to_expected", {})
        assert comparison.get("coverage_pct", 0) >= 90.0
        assert comparison.get("value_match_pct", 0) >= 90.0


@pytest.mark.slow
class TestTZOODraftCoverage:
    """Validate that the curate draft covers >=80% of expected.json FY fields."""

    def test_all_fy_periods_present_in_draft(self, tzoo_draft: dict) -> None:
        expected = json.loads(
            (CASES_DIR / "TZOO" / "expected.json").read_text(encoding="utf-8")
        )
        fy_periods = [p for p in expected["periods"] if p.startswith("FY")]
        draft_periods = set(tzoo_draft.get("periods", {}).keys())
        missing = [p for p in fy_periods if p not in draft_periods]
        assert not missing, f"FY periods missing from draft: {missing}"

    def test_fy_field_coverage_at_least_90pct(self, tzoo_draft: dict) -> None:
        expected = json.loads(
            (CASES_DIR / "TZOO" / "expected.json").read_text(encoding="utf-8")
        )
        fy_periods = [p for p in expected["periods"] if p.startswith("FY")]
        assert len(fy_periods) > 0

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
            f"({total_matched}/{total_expected_fields})"
        )


class TestSanityChecks:
    """Tests for run_sanity_checks() with handcrafted draft data."""

    def test_balance_sheet_inconsistency_triggers_warning(self) -> None:
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "total_assets": {"value": 100},
                        "total_liabilities": {"value": 60},
                        "total_equity": {"value": 10},
                    }
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert len(warnings) >= 1
        assert any("A≠L+E" in w for w in warnings)

    def test_balanced_sheet_produces_no_inequality_warning(self) -> None:
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "total_assets": {"value": 100},
                        "total_liabilities": {"value": 60},
                        "total_equity": {"value": 40},
                    }
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert not any("A≠L+E" in w for w in warnings)

    def test_negative_revenue_triggers_warning(self) -> None:
        draft = {"periods": {"FY2024": {"fields": {"ingresos": {"value": -1000}}}}}
        warnings = run_sanity_checks(draft)
        assert any("ingresos" in w for w in warnings)

    def test_opposing_ni_eps_signs_triggers_warning(self) -> None:
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "net_income": {"value": 1000},
                        "eps_basic": {"value": -1.50},
                    }
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert any("opposite signs" in w for w in warnings)

    def test_empty_periods_produces_no_warnings(self) -> None:
        assert run_sanity_checks({"periods": {}}) == []

    def test_well_formed_draft_no_warnings(self) -> None:
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "ingresos": {"value": 1_000_000},
                        "net_income": {"value": 50_000},
                        "eps_basic": {"value": 1.25},
                        "total_assets": {"value": 500_000},
                        "total_liabilities": {"value": 300_000},
                        "total_equity": {"value": 200_000},
                    }
                }
            }
        }
        assert run_sanity_checks(draft) == []
