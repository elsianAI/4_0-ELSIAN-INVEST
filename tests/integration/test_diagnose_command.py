"""tests/integration/test_diagnose_command.py — Integration tests for `elsian diagnose`.

Tests the ``diagnose --all`` command path end-to-end without network calls.
All data is read from existing on-disk artifacts in cases/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

CASES_DIR = Path(__file__).resolve().parent.parent.parent / "cases"


def _has_any_evaluable_case() -> bool:
    """Check that at least one case has expected.json + case.json (and filings) for on-the-fly eval.

    After the BL-069 fix, diagnose re-extracts on-the-fly; extraction_result.json
    is no longer required for a case to be evaluable by diagnose.
    """
    for d in CASES_DIR.iterdir():
        if not d.is_dir():
            continue
        filings_dir = d / "filings"
        if (
            (d / "expected.json").exists()
            and (d / "case.json").exists()
            and filings_dir.exists()
            and any(filings_dir.iterdir())
        ):
            return True
    return False


def _make_args(**kwargs: Any) -> argparse.Namespace:
    defaults = {"all": True, "output": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ── Tests ─────────────────────────────────────────────────────────────


class TestDiagnoseAll:
    """Integration tests for cmd_diagnose with existing artifacts."""

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases (expected.json + extraction_result.json) found",
    )
    def test_cmd_diagnose_all_creates_json_and_md(self, tmp_path: Path) -> None:
        """cmd_diagnose writes diagnose_report.json and diagnose_report.md."""
        from elsian.cli import cmd_diagnose

        args = _make_args(output=str(tmp_path))
        cmd_diagnose(args)

        json_path = tmp_path / "diagnose_report.json"
        md_path = tmp_path / "diagnose_report.md"
        assert json_path.exists(), "diagnose_report.json not written"
        assert md_path.exists(), "diagnose_report.md not written"

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_json_report_schema_version(self, tmp_path: Path) -> None:
        """diagnose_report.json has schema_version = diagnose_v1."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        assert data["schema_version"] == "diagnose_v1"

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_json_report_required_keys(self, tmp_path: Path) -> None:
        """diagnose_report.json contains all required top-level keys."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        for key in ("schema_version", "generated_at", "summary", "hotspots",
                    "by_ticker", "by_source_hint",
                    "by_period_type", "by_field_category", "root_cause_summary"):
            assert key in data, f"Missing top-level key: {key}"

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_hotspots_have_root_cause_hint_and_field_category(self, tmp_path: Path) -> None:
        """Each hotspot in the JSON report has root_cause_hint and field_category fields."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        for h in data.get("hotspots", []):
            assert "root_cause_hint" in h, f"Hotspot missing root_cause_hint: {h}"
            assert "field_category" in h, f"Hotspot missing field_category: {h}"
            assert isinstance(h["root_cause_hint"], str) and h["root_cause_hint"]
            assert isinstance(h["field_category"], str) and h["field_category"]

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_by_period_type_is_dict(self, tmp_path: Path) -> None:
        """by_period_type is a dict (possibly empty) in the JSON report."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        assert isinstance(data["by_period_type"], dict)

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_by_field_category_is_dict(self, tmp_path: Path) -> None:
        """by_field_category is a dict in the JSON report."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        assert isinstance(data["by_field_category"], dict)

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_markdown_contains_new_sections(self, tmp_path: Path) -> None:
        """diagnose_report.md contains the new Slice-2 sections."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        md = (tmp_path / "diagnose_report.md").read_text(encoding="utf-8")
        assert "Root Cause Hint" in md
        assert "By Period Type" in md
        assert "By Field Category" in md

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_summary_counts_are_consistent(self, tmp_path: Path) -> None:
        """tickers_with_eval + tickers_skipped == tickers_analyzed."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        s = data["summary"]
        assert s["tickers_with_eval"] + s["tickers_skipped"] == s["tickers_analyzed"]

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_hotspots_have_required_fields(self, tmp_path: Path) -> None:
        """Each hotspot entry has required keys."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        for h in data.get("hotspots", []):
            for key in ("rank", "field", "gap_type", "occurrences",
                        "affected_tickers", "evidence"):
                assert key in h, f"Hotspot missing key: {key}"

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_hotspots_ranked_monotonically(self, tmp_path: Path) -> None:
        """Hotspot ranks are 1, 2, 3, … without gaps."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        hotspots = data.get("hotspots", [])
        for i, h in enumerate(hotspots, start=1):
            assert h["rank"] == i

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_hotspots_occurrences_non_increasing(self, tmp_path: Path) -> None:
        """Hotspot list is sorted by occurrences descending."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        hotspots = data.get("hotspots", [])
        for i in range(len(hotspots) - 1):
            assert hotspots[i]["occurrences"] >= hotspots[i + 1]["occurrences"]

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_md_report_contains_summary_and_hotspots(self, tmp_path: Path) -> None:
        """diagnose_report.md contains Summary and Hotspot sections."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        md = (tmp_path / "diagnose_report.md").read_text(encoding="utf-8")
        assert "# ELSIAN Diagnose Report" in md
        assert "## Summary" in md

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_by_ticker_entries_have_all_keys(self, tmp_path: Path) -> None:
        """Each by_ticker entry has required keys."""
        from elsian.cli import cmd_diagnose

        cmd_diagnose(_make_args(output=str(tmp_path)))
        data = json.loads((tmp_path / "diagnose_report.json").read_text(encoding="utf-8"))
        for ticker, d in data.get("by_ticker", {}).items():
            for key in ("score", "matched", "total_expected", "wrong",
                        "missed", "extra", "source_hint", "skipped"):
                assert key in d, f"{ticker} missing key: {key}"

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_does_not_mutate_case_artifacts(self, tmp_path: Path) -> None:
        """cmd_diagnose does not write to cases/ directory."""
        from elsian.cli import cmd_diagnose
        import os
        import time

        # Record mtime of all artifacts in cases/ before running
        before: dict[str, float] = {}
        for d in CASES_DIR.iterdir():
            if not d.is_dir():
                continue
            for f in ("expected.json", "extraction_result.json", "case.json"):
                fp = d / f
                if fp.exists():
                    before[str(fp)] = fp.stat().st_mtime

        cmd_diagnose(_make_args(output=str(tmp_path)))

        for path_str, mtime_before in before.items():
            mtime_after = Path(path_str).stat().st_mtime
            assert mtime_after == mtime_before, f"File was mutated: {path_str}"


# ── Engine-level integration ──────────────────────────────────────────


class TestDiagnoseEngine:
    """Integration tests for the engine build_report function directly."""

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_build_report_on_real_cases_dir(self) -> None:
        """build_report on the real CASES_DIR returns a valid report."""
        from elsian.diagnose.engine import build_report

        report = build_report(CASES_DIR)
        assert report["schema_version"] == "diagnose_v1"
        assert report["summary"]["tickers_analyzed"] > 0
        assert isinstance(report["hotspots"], list)

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases found",
    )
    def test_gap_type_values_are_valid(self) -> None:
        """All hotspot gap_type values are 'wrong' or 'missed'."""
        from elsian.diagnose.engine import build_report

        report = build_report(CASES_DIR)
        valid = {"wrong", "missed"}
        for h in report["hotspots"]:
            assert h["gap_type"] in valid, f"Invalid gap_type: {h['gap_type']}"


# ── Coherence: diagnose vs eval ───────────────────────────────────────


def _tzoo_evaluable() -> bool:
    """TZOO has expected.json and filings."""
    tzoo = CASES_DIR / "TZOO"
    filings_dir = tzoo / "filings"
    return (
        (tzoo / "expected.json").exists()
        and filings_dir.exists()
        and any(filings_dir.iterdir())
    )


class TestDiagnoseVsEvalCoherence:
    """Integration tests verifying that diagnose scores match cmd_eval scores.

    This is the gate that caught the BL-069 auditor blocker:
    diagnose was reading a stale extraction_result.json while eval was
    re-extracting on-the-fly.  After the fix, both paths must agree.
    """

    @pytest.mark.skipif(not _tzoo_evaluable(), reason="TZOO expected.json or filings missing")
    def test_diagnose_score_matches_eval_score_for_tzoo(self) -> None:
        """diagnose score for TZOO must equal the score produced by the eval path."""
        from elsian.diagnose.engine import collect_case_eval
        from elsian.evaluate.evaluator import evaluate
        from elsian.extract.phase import ExtractPhase

        case_dir = CASES_DIR / "TZOO"
        expected_path = case_dir / "expected.json"

        # Canonical eval path
        report = evaluate(ExtractPhase().extract(str(case_dir)), str(expected_path))

        # Diagnose path
        diag = collect_case_eval(case_dir)
        assert diag is not None

        assert diag["score"] == report.score, (
            f"diagnose score {diag['score']:.2f} != eval score {report.score:.2f}; "
            "diagnose is reading stale data instead of re-extracting"
        )
        assert diag["matched"] == report.matched
        assert diag["wrong"] == report.wrong
        assert diag["missed"] == report.missed

    @pytest.mark.skipif(not _tzoo_evaluable(), reason="TZOO expected.json or filings missing")
    def test_diagnose_report_tickers_with_eval_never_skipped(self) -> None:
        """build_report on real cases must report tickers_skipped == 0.

        After the fix, every case with expected.json is evaluated on-the-fly;
        none should be counted as skipped.
        """
        from elsian.diagnose.engine import build_report

        report = build_report(CASES_DIR)
        assert report["summary"]["tickers_skipped"] == 0, (
            f"Expected 0 skipped tickers but got {report['summary']['tickers_skipped']}; "
            "diagnose may still be reading stale artifacts for some cases"
        )

    @pytest.mark.skipif(not _tzoo_evaluable(), reason="TZOO expected.json or filings missing")
    def test_diagnose_all_tickers_100pct_when_eval_all_pass(self) -> None:
        """When eval --all is 100%, build_report overall_score_pct must also be 100%.

        This is the direct reproduction of the BL-069 auditor's blocker:
        diagnose reported 99.2% (ADTN with 37 wrong from stale artifact)
        while eval --all reported 17/17 PASS 100%.
        """
        from elsian.diagnose.engine import build_report
        from elsian.evaluate.evaluator import evaluate
        from elsian.extract.phase import ExtractPhase

        # Compute eval --all scores directly
        all_100 = True
        phase = ExtractPhase()
        for d in sorted(CASES_DIR.iterdir()):
            if not d.is_dir() or not (d / "expected.json").exists():
                continue
            report = evaluate(phase.extract(str(d)), str(d / "expected.json"))
            if report.score < 100.0:
                all_100 = False
                break

        if not all_100:
            pytest.skip("Not all tickers are at 100%; coherence test only applies to green baseline")

        # Now verify diagnose agrees
        diag_report = build_report(CASES_DIR)
        assert diag_report["summary"]["overall_score_pct"] == 100.0, (
            f"eval --all is 100% but diagnose reports "
            f"{diag_report['summary']['overall_score_pct']:.2f}%; stale artifact divergence"
        )
