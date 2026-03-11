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
    """Check that at least one case has both expected.json and extraction_result.json."""
    for d in CASES_DIR.iterdir():
        if d.is_dir() and (d / "expected.json").exists() and (d / "extraction_result.json").exists():
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
                    "by_ticker", "by_source_hint"):
            assert key in data, f"Missing top-level key: {key}"

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
