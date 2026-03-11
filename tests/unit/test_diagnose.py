"""tests/unit/test_diagnose.py — Unit tests for BL-069 diagnose engine and renderer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── helpers ───────────────────────────────────────────────────────────

CASES_DIR = Path(__file__).resolve().parent.parent.parent / "cases"


def _has_extraction_result(ticker: str) -> bool:
    return (CASES_DIR / ticker / "extraction_result.json").exists()


def _has_expected(ticker: str) -> bool:
    return (CASES_DIR / ticker / "expected.json").exists()


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

    def test_returns_skipped_when_no_extraction_result(self, tmp_path: Path) -> None:
        """Returns skipped=True when extraction_result.json is absent."""
        from elsian.diagnose.engine import collect_case_eval

        case_dir = tmp_path / "FAKE2"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "FAKE2", "source_hint": "sec"}), encoding="utf-8"
        )
        (case_dir / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKE2", "periods": {}}),
            encoding="utf-8",
        )
        result = collect_case_eval(case_dir)
        assert result is not None
        assert result["skipped"] is True
        assert result["skip_reason"] == "no extraction_result.json"

    def test_returns_skip_reason_string(self, tmp_path: Path) -> None:
        """skip_reason is a non-empty string when skipped."""
        from elsian.diagnose.engine import collect_case_eval

        case_dir = tmp_path / "FAKE3"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "FAKE3", "source_hint": "asx"}), encoding="utf-8"
        )
        (case_dir / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKE3", "periods": {}}),
            encoding="utf-8",
        )
        result = collect_case_eval(case_dir)
        assert isinstance(result["skip_reason"], str)
        assert result["source_hint"] == "asx"

    @pytest.mark.skipif(
        not (_has_extraction_result("TZOO") and _has_expected("TZOO")),
        reason="TZOO artifacts not available",
    )
    def test_tzoo_eval_returns_expected_keys(self) -> None:
        """collect_case_eval on TZOO returns a dict with all required keys."""
        from elsian.diagnose.engine import collect_case_eval

        result = collect_case_eval(CASES_DIR / "TZOO")
        assert result is not None
        assert result["skipped"] is False
        for key in ("ticker", "score", "matched", "wrong", "missed", "extra",
                    "total_expected", "details", "source_hint", "fatal"):
            assert key in result, f"Missing key: {key}"

    @pytest.mark.skipif(
        not (_has_extraction_result("TZOO") and _has_expected("TZOO")),
        reason="TZOO artifacts not available",
    )
    def test_tzoo_details_are_non_matched_only(self) -> None:
        """details list contains only wrong/missed entries, never matched."""
        from elsian.diagnose.engine import collect_case_eval

        result = collect_case_eval(CASES_DIR / "TZOO")
        assert result is not None
        for d in result["details"]:
            assert d["gap_type"] != "matched"
            assert "field" in d
            assert "period" in d


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
        """A case with expected.json but no extraction_result.json is counted and skipped."""
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
        assert report["summary"]["tickers_skipped"] == 1
        assert report["summary"]["tickers_with_eval"] == 0

    @pytest.mark.skipif(
        not (_has_extraction_result("TZOO") and _has_expected("TZOO")),
        reason="TZOO artifacts not available",
    )
    def test_real_cases_dir_produces_nontrivial_report(self) -> None:
        from elsian.diagnose.engine import build_report

        report = build_report(CASES_DIR)
        assert report["summary"]["tickers_analyzed"] >= 1
        assert isinstance(report["hotspots"], list)
        assert isinstance(report["by_ticker"], dict)
        assert "TZOO" in report["by_ticker"]


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
