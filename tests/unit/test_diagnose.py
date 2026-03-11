"""tests/unit/test_diagnose.py — Unit tests for BL-069 diagnose engine and renderer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# ── helpers ───────────────────────────────────────────────────────────

CASES_DIR = Path(__file__).resolve().parent.parent.parent / "cases"


def _has_expected(ticker: str) -> bool:
    return (CASES_DIR / ticker / "expected.json").exists()


def _has_filings(ticker: str) -> bool:
    filings_dir = CASES_DIR / ticker / "filings"
    return filings_dir.exists() and any(filings_dir.iterdir())


# ── collect_case_eval ─────────────────────────────────────────────────


class TestCollectCaseEval:
    """Unit tests for engine.collect_case_eval."""

    def test_returns_none_when_no_expected(self, tmp_path: Path) -> None:
        """Returns None when no expected.json is present."""
        from elsian.diagnose.engine import collect_case_eval

        case_dir = tmp_path / "FAKE"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "FAKE", "source_hint": "sec"}), encoding="utf-8"
        )
        assert collect_case_eval(case_dir) is None

    def test_case_with_no_filings_evaluates_on_the_fly(self, tmp_path: Path) -> None:
        """A case with expected.json but no filings still evaluates (score=0, never skipped).

        diagnose now re-extracts on-the-fly (same as cmd_eval) instead of
        loading a potentially stale extraction_result.json.  A case with no
        filings produces an empty extraction, so all expected fields are missed
        and score=0.0 — but the result is *not* skipped; it is a live eval.
        """
        from elsian.diagnose.engine import collect_case_eval

        case_dir = tmp_path / "NOFIL"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "NOFIL", "source_hint": "sec"}), encoding="utf-8"
        )
        (case_dir / "expected.json").write_text(
            json.dumps({
                "version": "1.0", "ticker": "NOFIL",
                "periods": {
                    "FY2024": {
                        "fecha_fin": "2024-12-31",
                        "tipo_periodo": "anual",
                        "fields": {
                            "ingresos": {"value": 1000.0, "source_filing": "x.txt"}
                        },
                    }
                },
            }),
            encoding="utf-8",
        )
        # No filings/ dir → ExtractPhase returns empty result → all expected missed
        result = collect_case_eval(case_dir)
        assert result is not None
        assert result["skipped"] is False, "diagnose must never skip due to missing artifact"
        assert result["skip_reason"] is None
        assert result["matched"] == 0
        assert result["total_expected"] == 1
        assert result["missed"] == 1
        assert result["score"] == 0.0

    def test_skipped_is_always_false(self, tmp_path: Path) -> None:
        """collect_case_eval never returns skipped=True for any case with expected.json."""
        from elsian.diagnose.engine import collect_case_eval

        case_dir = tmp_path / "NOART"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "NOART", "source_hint": "asx"}), encoding="utf-8"
        )
        (case_dir / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "NOART", "periods": {}}),
            encoding="utf-8",
        )
        result = collect_case_eval(case_dir)
        assert result is not None
        assert result["skipped"] is False
        assert result["source_hint"] == "asx"

    def test_collect_case_eval_calls_extract_phase_not_artifact(self, tmp_path: Path) -> None:
        """collect_case_eval calls ExtractPhase.extract(), NOT extraction_result.json.

        This is the unit-level gate for the BL-069 fix: diagnose must use the
        live extraction path, never a potentially stale persisted artifact.
        Even when extraction_result.json is present with different data, it must
        be ignored.
        """
        from elsian.diagnose.engine import collect_case_eval
        from elsian.models.result import ExtractionResult

        case_dir = tmp_path / "MOCK"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "MOCK", "source_hint": "sec"}), encoding="utf-8"
        )
        (case_dir / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "MOCK", "periods": {}}),
            encoding="utf-8",
        )
        # Stale artifact with filings_used=99 — must NOT be read by diagnose
        (case_dir / "extraction_result.json").write_text(
            json.dumps({
                "ticker": "MOCK", "currency": "USD",
                "periods": {}, "filings_used": 99, "schema_version": "2.0",
            }),
            encoding="utf-8",
        )

        mock_result = ExtractionResult(ticker="MOCK", currency="USD", filings_used=0)
        with patch("elsian.extract.phase.ExtractPhase.extract", return_value=mock_result) as mock_extract:
            result = collect_case_eval(case_dir)
            mock_extract.assert_called_once_with(str(case_dir))

        assert result is not None
        assert result["skipped"] is False, "diagnose must never skip due to missing/stale artifact"

    def test_stale_artifact_does_not_influence_result(self, tmp_path: Path) -> None:
        """A stale extraction_result.json with different data does not affect the diagnose result.

        The score must come from ExtractPhase.extract(), not from the persisted JSON.  We
        inject a mock that returns a custom result and verify the case eval reflects it.
        """
        from elsian.diagnose.engine import collect_case_eval
        from elsian.models.result import ExtractionResult, PeriodResult
        from elsian.models.field import FieldResult, Provenance

        case_dir = tmp_path / "STALE"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "STALE", "source_hint": "sec"}), encoding="utf-8"
        )
        (case_dir / "expected.json").write_text(
            json.dumps({
                "version": "1.0", "ticker": "STALE",
                "periods": {
                    "FY2024": {
                        "fecha_fin": "2024-12-31",
                        "tipo_periodo": "anual",
                        "fields": {
                            "ingresos": {"value": 1000.0, "source_filing": "x.txt"}
                        },
                    }
                },
            }),
            encoding="utf-8",
        )
        # Stale artifact says ingresos=999 (wrong) — must NOT be used
        (case_dir / "extraction_result.json").write_text(
            json.dumps({
                "ticker": "STALE", "currency": "USD", "schema_version": "2.0",
                "filings_used": 1,
                "periods": {
                    "FY2024": {
                        "fecha_fin": "2024-12-31",
                        "tipo_periodo": "anual",
                        "fields": {
                            "ingresos": {
                                "value": 999.0,
                                "source_filing": "x.txt",
                                "source_location": "",
                                "scale": "raw",
                                "confidence": "high",
                            },
                        },
                    }
                },
            }),
            encoding="utf-8",
        )

        # Mock ExtractPhase to return the CORRECT value (1000.0 = match)
        mock_result = ExtractionResult(ticker="STALE", currency="USD", filings_used=1)
        mock_period = PeriodResult(fecha_fin="2024-12-31", tipo_periodo="anual")
        mock_period.fields["ingresos"] = FieldResult(
            value=1000.0,
            provenance=Provenance(source_filing="x.txt", source_location=""),
            scale="raw",
            confidence="high",
        )
        mock_result.periods["FY2024"] = mock_period

        with patch("elsian.extract.phase.ExtractPhase.extract", return_value=mock_result):
            result = collect_case_eval(case_dir)

        assert result is not None
        assert result["score"] == 100.0, (
            f"Expected 100.0 from fresh extraction but got {result['score']}; "
            "diagnose may be reading the stale artifact (injected value 999)"
        )
        assert result["matched"] == 1
        assert result["wrong"] == 0


# ── aggregate_hotspots ────────────────────────────────────────────────


class TestAggregateHotspots:
    """Unit tests for engine.aggregate_hotspots."""

    def test_empty_input_returns_empty_list(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots

        assert aggregate_hotspots([]) == []

    def test_skipped_cases_are_ignored(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots

        cases = [{"ticker": "X", "skipped": True, "details": [
            {"field": "ingresos", "period": "FY2024", "gap_type": "missed", "expected": 100.0, "actual": None}
        ]}]
        assert aggregate_hotspots(cases) == []

    def test_groups_by_field_and_gap_type(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots

        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "details": [
                    {"field": "net_income", "period": "FY2024", "gap_type": "missed", "expected": 10.0, "actual": None},
                    {"field": "ebitda", "period": "FY2024", "gap_type": "wrong", "expected": 50.0, "actual": 40.0},
                ],
            },
            {
                "ticker": "B",
                "skipped": False,
                "details": [
                    {"field": "net_income", "period": "FY2024", "gap_type": "missed", "expected": 20.0, "actual": None},
                ],
            },
        ]
        hotspots = aggregate_hotspots(cases)
        # net_income/missed has 2 occurrences → rank 1
        assert hotspots[0]["field"] == "net_income"
        assert hotspots[0]["gap_type"] == "missed"
        assert hotspots[0]["occurrences"] == 2
        assert sorted(hotspots[0]["affected_tickers"]) == ["A", "B"]

    def test_ranks_by_occurrences_descending(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots

        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "details": [
                    {"field": "rare_field", "period": "FY2024", "gap_type": "missed", "expected": 1.0, "actual": None},
                ],
            },
            {
                "ticker": "B",
                "skipped": False,
                "details": [
                    {"field": "common_field", "period": "FY2024", "gap_type": "wrong", "expected": 2.0, "actual": 1.0},
                ],
            },
            {
                "ticker": "C",
                "skipped": False,
                "details": [
                    {"field": "common_field", "period": "FY2024", "gap_type": "wrong", "expected": 3.0, "actual": 2.0},
                ],
            },
        ]
        hotspots = aggregate_hotspots(cases)
        assert hotspots[0]["field"] == "common_field"
        assert hotspots[0]["occurrences"] == 2

    def test_evidence_capped_at_3_samples(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots

        cases = [
            {
                "ticker": chr(65 + i),  # A, B, C, D, E
                "skipped": False,
                "details": [
                    {"field": "ingresos", "period": "FY2024", "gap_type": "missed", "expected": float(i), "actual": None}
                ],
            }
            for i in range(5)
        ]
        hotspots = aggregate_hotspots(cases)
        assert hotspots[0]["occurrences"] == 5
        assert len(hotspots[0]["evidence"]) <= 3

    def test_rank_is_1_indexed(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots

        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "details": [
                    {"field": "f1", "period": "FY2024", "gap_type": "missed", "expected": 1.0, "actual": None}
                ],
            }
        ]
        hotspots = aggregate_hotspots(cases)
        assert hotspots[0]["rank"] == 1


# ── build_report ──────────────────────────────────────────────────────


class TestBuildReport:
    """Unit tests for engine.build_report."""

    def test_empty_cases_dir_returns_valid_structure(self, tmp_path: Path) -> None:
        """build_report on an empty dir returns a valid report with zero counts."""
        from elsian.diagnose.engine import build_report

        report = build_report(tmp_path)
        assert report["schema_version"] == "diagnose_v1"
        assert "summary" in report
        assert "hotspots" in report
        assert "by_ticker" in report
        assert "by_source_hint" in report
        assert report["summary"]["tickers_analyzed"] == 0

    def test_report_summary_keys(self, tmp_path: Path) -> None:
        from elsian.diagnose.engine import build_report

        report = build_report(tmp_path)
        summary = report["summary"]
        for key in (
            "tickers_analyzed", "tickers_with_eval", "tickers_skipped",
            "total_expected", "total_matched", "total_wrong",
            "total_missed", "total_extra", "overall_score_pct",
        ):
            assert key in summary, f"Missing summary key: {key}"

    def test_skipped_case_counted_in_tickers_analyzed(self, tmp_path: Path) -> None:
        """A case with expected.json but no filings is now evaluated on-the-fly (not skipped).

        Before the BL-069 fix, absence of extraction_result.json caused
        tickers_skipped to increment.  After the fix, diagnose always
        re-extracts, so every case with expected.json contributes to
        tickers_with_eval (never tickers_skipped).
        """
        from elsian.diagnose.engine import build_report

        case_dir = tmp_path / "FAKE"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "FAKE", "source_hint": "sec"}), encoding="utf-8"
        )
        (case_dir / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKE", "periods": {}}),
            encoding="utf-8",
        )
        report = build_report(tmp_path)
        assert report["summary"]["tickers_analyzed"] == 1
        # No longer skipped — always re-extracts on-the-fly
        assert report["summary"]["tickers_skipped"] == 0
        assert report["summary"]["tickers_with_eval"] == 1

    @pytest.mark.skipif(
        not _has_expected("TZOO"),
        reason="TZOO expected.json not available",
    )
    def test_real_cases_dir_produces_nontrivial_report_mocked(self) -> None:
        """build_report with mocked ExtractPhase returns a valid non-empty report structure.

        This test uses a mock to avoid slow real extraction of all cases.
        Heavy coherence testing (verifying actual scores agree with eval) lives
        in tests/integration/test_diagnose_command.py:TestDiagnoseVsEvalCoherence.
        """
        from elsian.diagnose.engine import build_report
        from elsian.models.result import ExtractionResult

        empty_result = ExtractionResult(ticker="TZOO", currency="USD", filings_used=0)
        with patch("elsian.extract.phase.ExtractPhase.extract", return_value=empty_result):
            report = build_report(CASES_DIR)
        assert report["schema_version"] == "diagnose_v1"
        assert report["summary"]["tickers_analyzed"] >= 1
        assert isinstance(report["hotspots"], list)
        assert isinstance(report["by_ticker"], dict)


# ── render_markdown ───────────────────────────────────────────────────


class TestRenderMarkdown:
    """Unit tests for render.render_markdown."""

    def _minimal_report(self) -> dict:
        return {
            "schema_version": "diagnose_v1",
            "generated_at": "2026-03-11T00:00:00+00:00",
            "cases_dir": "/tmp/cases",
            "summary": {
                "tickers_analyzed": 2,
                "tickers_with_eval": 1,
                "tickers_skipped": 1,
                "total_expected": 10,
                "total_matched": 8,
                "total_wrong": 1,
                "total_missed": 1,
                "total_extra": 3,
                "overall_score_pct": 80.0,
            },
            "hotspots": [
                {
                    "rank": 1,
                    "field": "net_income",
                    "gap_type": "missed",
                    "occurrences": 2,
                    "affected_tickers": ["A", "B"],
                    "evidence": [
                        {"ticker": "A", "period": "FY2024", "expected": 100.0, "actual": None}
                    ],
                }
            ],
            "by_ticker": {
                "A": {
                    "score": 80.0, "matched": 8, "total_expected": 10,
                    "wrong": 1, "missed": 1, "extra": 3,
                    "source_hint": "sec", "skipped": False, "skip_reason": None, "fatal": False,
                }
            },
            "by_source_hint": {
                "sec": {
                    "tickers": ["A"],
                    "avg_score_pct": 80.0,
                    "total_wrong": 1,
                    "total_missed": 1,
                    "total_expected": 10,
                }
            },
        }

    def test_output_is_string(self) -> None:
        from elsian.diagnose.render import render_markdown

        md = render_markdown(self._minimal_report())
        assert isinstance(md, str)
        assert len(md) > 0

    def test_contains_summary_section(self) -> None:
        from elsian.diagnose.render import render_markdown

        md = render_markdown(self._minimal_report())
        assert "## Summary" in md
        assert "Overall score" in md

    def test_contains_hotspots_section(self) -> None:
        from elsian.diagnose.render import render_markdown

        md = render_markdown(self._minimal_report())
        assert "Hotspot" in md
        assert "net_income" in md
        assert "missed" in md

    def test_contains_per_ticker_section(self) -> None:
        from elsian.diagnose.render import render_markdown

        md = render_markdown(self._minimal_report())
        assert "Per-Ticker" in md
        assert "| A |" in md or "A" in md

    def test_contains_by_source_section(self) -> None:
        from elsian.diagnose.render import render_markdown

        md = render_markdown(self._minimal_report())
        assert "Source" in md
        assert "sec" in md

    def test_empty_report_does_not_raise(self) -> None:
        from elsian.diagnose.render import render_markdown

        md = render_markdown({
            "schema_version": "diagnose_v1",
            "generated_at": "",
            "cases_dir": "",
            "summary": {
                "tickers_analyzed": 0, "tickers_with_eval": 0, "tickers_skipped": 0,
                "total_expected": 0, "total_matched": 0, "total_wrong": 0,
                "total_missed": 0, "total_extra": 0, "overall_score_pct": 0.0,
            },
            "hotspots": [],
            "by_ticker": {},
            "by_source_hint": {},
        })
        assert "ELSIAN Diagnose Report" in md


# ── field_category ────────────────────────────────────────────────────


class TestFieldCategory:
    """Unit tests for engine.field_category."""

    def test_income_statement_field(self) -> None:
        from elsian.diagnose.engine import field_category
        assert field_category("net_income") == "income_statement"
        assert field_category("ingresos") == "income_statement"
        assert field_category("ebitda") == "income_statement"
        assert field_category("depreciation_amortization") == "income_statement"

    def test_per_share_field(self) -> None:
        from elsian.diagnose.engine import field_category
        assert field_category("eps_basic") == "per_share"
        assert field_category("eps_diluted") == "per_share"
        assert field_category("shares_outstanding") == "per_share"

    def test_balance_sheet_field(self) -> None:
        from elsian.diagnose.engine import field_category
        assert field_category("total_assets") == "balance_sheet"
        assert field_category("total_equity") == "balance_sheet"
        assert field_category("cash_and_equivalents") == "balance_sheet"

    def test_balance_sheet_extended_fields(self) -> None:
        """accounts_payable, accounts_receivable, inventories must map to balance_sheet."""
        from elsian.diagnose.engine import field_category
        assert field_category("accounts_payable") == "balance_sheet"
        assert field_category("accounts_receivable") == "balance_sheet"
        assert field_category("inventories") == "balance_sheet"

    def test_cash_flow_field(self) -> None:
        from elsian.diagnose.engine import field_category
        assert field_category("cfo") == "cash_flow"
        assert field_category("capex") == "cash_flow"
        assert field_category("fcf") == "cash_flow"

    def test_cash_flow_extended_fields(self) -> None:
        """cfi, cff, delta_cash must map to cash_flow."""
        from elsian.diagnose.engine import field_category
        assert field_category("cfi") == "cash_flow"
        assert field_category("cff") == "cash_flow"
        assert field_category("delta_cash") == "cash_flow"

    def test_unknown_field_returns_other(self) -> None:
        from elsian.diagnose.engine import field_category
        assert field_category("some_unknown_field") == "other"
        assert field_category("") == "other"


# ── _classify_root_cause_hint ─────────────────────────────────────────


class TestClassifyRootCauseHint:
    """Unit tests for engine._classify_root_cause_hint."""

    def _hint(self, gap_type, evidence, fatal_frac=0.0, period_map_frac=0.0):
        from elsian.diagnose.engine import _classify_root_cause_hint
        return _classify_root_cause_hint(gap_type, evidence, fatal_frac, period_map_frac)

    def test_missed_default_is_missing_extraction(self) -> None:
        assert self._hint("missed", []) == "missing_extraction"

    def test_fatal_upstream_when_high_fatal_fraction(self) -> None:
        assert self._hint("missed", [], fatal_frac=0.5) == "fatal_upstream"
        assert self._hint("missed", [], fatal_frac=1.0) == "fatal_upstream"

    def test_period_mapping_failure_when_high_period_miss(self) -> None:
        assert self._hint("missed", [], period_map_frac=0.6) == "period_mapping_failure"
        assert self._hint("missed", [], period_map_frac=1.0) == "period_mapping_failure"

    def test_fatal_takes_priority_over_period_mapping(self) -> None:
        # fatal_fraction >= 0.5 wins even if period_map_frac is also high
        assert self._hint("missed", [], fatal_frac=0.7, period_map_frac=0.8) == "fatal_upstream"

    def test_scale_1k_detected(self) -> None:
        evidence = [
            {"expected": 3.0, "actual": 3000.0},
            {"expected": 2.7, "actual": 2700.0},
        ]
        assert self._hint("wrong", evidence) == "scale_1k"

    def test_scale_001_detected(self) -> None:
        evidence = [{"expected": 3000.0, "actual": 3.0}]
        assert self._hint("wrong", evidence) == "scale_001"

    def test_scale_100_detected(self) -> None:
        evidence = [{"expected": 1.0, "actual": 100.0}]
        assert self._hint("wrong", evidence) == "scale_100"

    def test_sign_mismatch_detected(self) -> None:
        evidence = [{"expected": 100.0, "actual": -100.0}]
        assert self._hint("wrong", evidence) == "sign_mismatch"

    def test_value_deviation_default_for_wrong(self) -> None:
        evidence = [{"expected": 100.0, "actual": 85.0}]
        assert self._hint("wrong", evidence) == "value_deviation"

    def test_no_ratios_returns_value_deviation(self) -> None:
        # actual=None → no ratio computed
        evidence = [{"expected": 100.0, "actual": None}]
        assert self._hint("wrong", evidence) == "value_deviation"

    def test_zero_expected_not_included_in_ratio(self) -> None:
        # expected=0 would cause division by zero; should gracefully return value_deviation
        evidence = [{"expected": 0.0, "actual": 1000.0}]
        assert self._hint("wrong", evidence) == "value_deviation"


# ── aggregate_by_period_type ──────────────────────────────────────────


class TestAggregateByPeriodType:
    """Unit tests for engine.aggregate_by_period_type."""

    def test_empty_input_returns_empty_dict(self) -> None:
        from elsian.diagnose.engine import aggregate_by_period_type
        assert aggregate_by_period_type([]) == {}

    def test_skipped_cases_are_ignored(self) -> None:
        from elsian.diagnose.engine import aggregate_by_period_type
        cases = [{"ticker": "X", "skipped": True, "details": [
            {"field": "ingresos", "period": "FY2024", "tipo_periodo": "anual",
             "gap_type": "missed", "expected": 100.0, "actual": None, "period_miss_rate": 0.1}
        ]}]
        result = aggregate_by_period_type(cases)
        assert result == {}

    def test_groups_by_tipo_periodo(self) -> None:
        from elsian.diagnose.engine import aggregate_by_period_type
        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "details": [
                    {"field": "ingresos", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "missed", "expected": 100.0, "actual": None, "period_miss_rate": 0.1},
                    {"field": "net_income", "period": "Q1-2024", "tipo_periodo": "trimestral",
                     "gap_type": "wrong", "expected": 10.0, "actual": 11.0, "period_miss_rate": 0.0},
                ],
            },
            {
                "ticker": "B",
                "skipped": False,
                "details": [
                    {"field": "ebit", "period": "FY2023", "tipo_periodo": "anual",
                     "gap_type": "wrong", "expected": 50.0, "actual": 45.0, "period_miss_rate": 0.0},
                ],
            },
        ]
        result = aggregate_by_period_type(cases)
        assert "anual" in result
        assert "trimestral" in result
        assert result["anual"]["occurrences"] == 2
        assert result["anual"]["missed"] == 1
        assert result["anual"]["wrong"] == 1
        assert result["trimestral"]["occurrences"] == 1
        assert result["trimestral"]["wrong"] == 1
        assert sorted(result["anual"]["affected_tickers"]) == ["A", "B"]

    def test_missing_tipo_periodo_maps_to_unknown(self) -> None:
        from elsian.diagnose.engine import aggregate_by_period_type
        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "details": [
                    {"field": "ingresos", "period": "FY2024",
                     "gap_type": "missed", "expected": 100.0, "actual": None, "period_miss_rate": 0.0},
                    # No "tipo_periodo" key
                ],
            }
        ]
        result = aggregate_by_period_type(cases)
        assert "unknown" in result
        assert result["unknown"]["occurrences"] == 1


# ── aggregate_by_field_category ───────────────────────────────────────


class TestAggregateByFieldCategory:
    """Unit tests for engine.aggregate_by_field_category."""

    def test_empty_input_returns_empty_dict(self) -> None:
        from elsian.diagnose.engine import aggregate_by_field_category
        assert aggregate_by_field_category([]) == {}

    def test_skipped_cases_are_ignored(self) -> None:
        from elsian.diagnose.engine import aggregate_by_field_category
        cases = [{"ticker": "X", "skipped": True, "details": [
            {"field": "ingresos", "period": "FY2024", "tipo_periodo": "anual",
             "gap_type": "missed", "expected": 100.0, "actual": None, "period_miss_rate": 0.0}
        ]}]
        assert aggregate_by_field_category(cases) == {}

    def test_groups_by_category(self) -> None:
        from elsian.diagnose.engine import aggregate_by_field_category
        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "details": [
                    {"field": "net_income", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "missed", "expected": 10.0, "actual": None, "period_miss_rate": 0.0},
                    {"field": "ebitda", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "wrong", "expected": 50.0, "actual": 45.0, "period_miss_rate": 0.0},
                    {"field": "total_assets", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "missed", "expected": 100.0, "actual": None, "period_miss_rate": 0.0},
                ],
            }
        ]
        result = aggregate_by_field_category(cases)
        assert "income_statement" in result
        assert "balance_sheet" in result
        assert result["income_statement"]["occurrences"] == 2
        assert result["income_statement"]["wrong"] == 1
        assert result["income_statement"]["missed"] == 1
        assert "net_income" in result["income_statement"]["fields_with_gaps"]
        assert "ebitda" in result["income_statement"]["fields_with_gaps"]
        assert result["balance_sheet"]["occurrences"] == 1

    def test_unknown_field_goes_to_other_category(self) -> None:
        from elsian.diagnose.engine import aggregate_by_field_category
        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "details": [
                    {"field": "some_noncanonical_field", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "wrong", "expected": 100.0, "actual": 90.0, "period_miss_rate": 0.0},
                ],
            }
        ]
        result = aggregate_by_field_category(cases)
        assert "other" in result
        assert "some_noncanonical_field" in result["other"]["fields_with_gaps"]


# ── Extended aggregate_hotspots tests ─────────────────────────────────


class TestAggregateHotspotsSlice2:
    """Slice-2 extensions: root_cause_hint and field_category in hotspots."""

    def test_hotspots_have_root_cause_hint(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots
        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "fatal": False,
                "details": [
                    {"field": "net_income", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "missed", "expected": 10.0, "actual": None, "period_miss_rate": 0.1}
                ],
            }
        ]
        hotspots = aggregate_hotspots(cases)
        assert "root_cause_hint" in hotspots[0]
        assert isinstance(hotspots[0]["root_cause_hint"], str)
        assert len(hotspots[0]["root_cause_hint"]) > 0

    def test_hotspots_have_field_category(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots
        cases = [
            {
                "ticker": "A",
                "skipped": False,
                "fatal": False,
                "details": [
                    {"field": "net_income", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "missed", "expected": 10.0, "actual": None, "period_miss_rate": 0.0}
                ],
            }
        ]
        hotspots = aggregate_hotspots(cases)
        assert hotspots[0]["field_category"] == "income_statement"

    def test_scale_1k_hint_detected_from_evidence(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots
        cases = [
            {
                "ticker": "X",
                "skipped": False,
                "fatal": False,
                "details": [
                    {"field": "depreciation_amortization", "period": "Q1-2024",
                     "tipo_periodo": "trimestral", "gap_type": "wrong",
                     "expected": 3.0, "actual": 3000.0, "period_miss_rate": 0.0},
                ],
            }
        ]
        hotspots = aggregate_hotspots(cases)
        assert hotspots[0]["root_cause_hint"] == "scale_1k"

    def test_fatal_upstream_hint_when_ticker_fatal(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots
        cases = [
            {
                "ticker": "Y",
                "skipped": False,
                "fatal": True,
                "details": [
                    {"field": "ingresos", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "missed", "expected": 100.0, "actual": None, "period_miss_rate": 0.0},
                ],
            }
        ]
        hotspots = aggregate_hotspots(cases)
        assert hotspots[0]["root_cause_hint"] == "fatal_upstream"

    def test_period_mapping_failure_hint_when_high_miss_rate(self) -> None:
        from elsian.diagnose.engine import aggregate_hotspots
        # All 3 occurrences have period_miss_rate > 0.5 → period_mapping_failure
        cases = [
            {
                "ticker": chr(65 + i),
                "skipped": False,
                "fatal": False,
                "details": [
                    {"field": "ingresos", "period": "FY2024", "tipo_periodo": "anual",
                     "gap_type": "missed", "expected": 100.0, "actual": None,
                     "period_miss_rate": 0.8},
                ],
            }
            for i in range(3)
        ]
        hotspots = aggregate_hotspots(cases)
        assert hotspots[0]["root_cause_hint"] == "period_mapping_failure"


# ── Extended build_report tests ───────────────────────────────────────


class TestBuildReportSlice2:
    """Slice-2 extensions: new top-level keys in build_report output."""

    def test_report_has_by_period_type_key(self, tmp_path: Path) -> None:
        from elsian.diagnose.engine import build_report
        report = build_report(tmp_path)
        assert "by_period_type" in report

    def test_report_has_by_field_category_key(self, tmp_path: Path) -> None:
        from elsian.diagnose.engine import build_report
        report = build_report(tmp_path)
        assert "by_field_category" in report

    def test_report_has_root_cause_summary_key(self, tmp_path: Path) -> None:
        from elsian.diagnose.engine import build_report
        report = build_report(tmp_path)
        assert "root_cause_summary" in report

    def test_empty_cases_by_period_type_is_dict(self, tmp_path: Path) -> None:
        from elsian.diagnose.engine import build_report
        report = build_report(tmp_path)
        assert isinstance(report["by_period_type"], dict)

    def test_empty_cases_by_field_category_is_dict(self, tmp_path: Path) -> None:
        from elsian.diagnose.engine import build_report
        report = build_report(tmp_path)
        assert isinstance(report["by_field_category"], dict)

    def test_empty_cases_root_cause_summary_is_dict(self, tmp_path: Path) -> None:
        from elsian.diagnose.engine import build_report
        report = build_report(tmp_path)
        assert isinstance(report["root_cause_summary"], dict)

    @pytest.mark.skipif(
        not _has_expected("TZOO"),
        reason="TZOO expected.json not available",
    )
    def test_real_report_root_cause_summary_is_non_empty(self) -> None:
        """root_cause_summary is a dict even when called with all cases (mocked extract)."""
        from elsian.diagnose.engine import build_report
        from elsian.models.result import ExtractionResult

        empty_result = ExtractionResult(ticker="X", currency="USD", filings_used=0)
        with patch("elsian.extract.phase.ExtractPhase.extract", return_value=empty_result):
            report = build_report()
        assert isinstance(report["root_cause_summary"], dict)


# ── Extended render tests ─────────────────────────────────────────────


class TestRenderMarkdownSlice2:
    """Slice-2 render: new sections appear in Markdown output."""

    def _report_with_new_axes(self) -> dict:
        return {
            "schema_version": "diagnose_v1",
            "generated_at": "2026-03-11T00:00:00+00:00",
            "cases_dir": "/tmp",
            "summary": {
                "tickers_analyzed": 1, "tickers_with_eval": 1, "tickers_skipped": 0,
                "total_expected": 5, "total_matched": 3, "total_wrong": 1,
                "total_missed": 1, "total_extra": 0, "overall_score_pct": 60.0,
            },
            "hotspots": [
                {
                    "rank": 1, "field": "depreciation_amortization",
                    "field_category": "income_statement",
                    "gap_type": "wrong", "occurrences": 1,
                    "affected_tickers": ["X"], "root_cause_hint": "scale_1k",
                    "evidence": [{"ticker": "X", "period": "Q1-2024", "expected": 3.0, "actual": 3000.0}],
                }
            ],
            "by_ticker": {},
            "by_source_hint": {},
            "by_period_type": {
                "trimestral": {"occurrences": 1, "wrong": 1, "missed": 0, "affected_tickers": ["X"]},
            },
            "by_field_category": {
                "income_statement": {"occurrences": 1, "wrong": 1, "missed": 0,
                                     "fields_with_gaps": ["depreciation_amortization"]},
            },
            "root_cause_summary": {"scale_1k": 1},
        }

    def test_hotspot_table_has_root_cause_hint(self) -> None:
        from elsian.diagnose.render import render_markdown
        md = render_markdown(self._report_with_new_axes())
        assert "Root Cause Hint" in md
        assert "scale_1k" in md

    def test_hotspot_table_has_field_category(self) -> None:
        from elsian.diagnose.render import render_markdown
        md = render_markdown(self._report_with_new_axes())
        assert "Category" in md
        assert "income_statement" in md

    def test_root_cause_summary_section_rendered(self) -> None:
        from elsian.diagnose.render import render_markdown
        md = render_markdown(self._report_with_new_axes())
        assert "Root Cause Hint Summary" in md
        assert "scale_1k" in md

    def test_by_period_type_section_rendered(self) -> None:
        from elsian.diagnose.render import render_markdown
        md = render_markdown(self._report_with_new_axes())
        assert "By Period Type" in md
        assert "trimestral" in md

    def test_by_field_category_section_rendered(self) -> None:
        from elsian.diagnose.render import render_markdown
        md = render_markdown(self._report_with_new_axes())
        assert "By Field Category" in md
        assert "income_statement" in md
        assert "depreciation_amortization" in md
