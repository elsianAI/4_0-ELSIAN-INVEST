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


# ── Module-scoped cached fixtures ─────────────────────────────────────


@pytest.fixture(scope="module")
def _case_mtimes_before():  # type: ignore[no-untyped-def]
    """Snapshot of all case artifact mtimes *before* any diagnose run.

    Must be listed as a dependency of ``shared_diagnose_result`` so pytest
    guarantees it runs before cmd_diagnose modifies any file.
    """
    mtimes: dict[str, float] = {}
    for d in CASES_DIR.iterdir():
        if not d.is_dir():
            continue
        for fname in ("expected.json", "extraction_result.json", "case.json"):
            fp = d / fname
            if fp.exists():
                mtimes[str(fp)] = fp.stat().st_mtime
    return mtimes


@pytest.fixture(scope="module")
def shared_diagnose_result(tmp_path_factory, _case_mtimes_before):  # type: ignore[no-untyped-def]
    """Run cmd_diagnose --all **once** per module; share output across all tests.

    ``_case_mtimes_before`` is listed as a dependency so the mtime snapshot
    is captured before cmd_diagnose runs.

    Returns ``(output_dir: Path, report_data: dict)``.
    Skips the whole module if no evaluable cases exist.
    """
    if not _has_any_evaluable_case():
        pytest.skip("No evaluable cases found")
    from elsian.cli import cmd_diagnose

    out = tmp_path_factory.mktemp("diagnose_shared")
    cmd_diagnose(_make_args(output=str(out)))
    data = json.loads((out / "diagnose_report.json").read_text(encoding="utf-8"))
    return out, data


@pytest.fixture(scope="module")
def engine_report(shared_diagnose_result):  # type: ignore[no-untyped-def]
    """Return the report dict produced by build_report during the shared diagnose run.

    cmd_diagnose calls build_report internally; this fixture reuses that result
    to avoid a second full extraction pass across all cases.
    """
    _, data = shared_diagnose_result
    return data


# ── Tests ─────────────────────────────────────────────────────────────


class TestDiagnoseAllEnforcement:
    """Tests for --all enforcement gate in cmd_diagnose."""

    def test_requires_all_flag(self) -> None:
        """cmd_diagnose raises SystemExit(1) when --all is not provided."""
        from elsian.cli import cmd_diagnose

        args = _make_args(all=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_diagnose(args)
        assert exc_info.value.code == 1

    def test_all_flag_missing_message(self, capsys: pytest.CaptureFixture) -> None:
        """cmd_diagnose prints the required error message when --all is absent."""
        from elsian.cli import cmd_diagnose

        args = _make_args(all=False)
        with pytest.raises(SystemExit):
            cmd_diagnose(args)
        captured = capsys.readouterr()
        assert "--all is required" in captured.out

    def test_default_output_writes_to_tempdir_not_repo(self) -> None:
        """cmd_diagnose with no --output must NOT write into the repo tree.

        The output directory must be a system temporary directory, not
        CASES_DIR.parent (which is the repo root).
        """
        from unittest.mock import patch
        from elsian.cli import cmd_diagnose, CASES_DIR

        repo_root = CASES_DIR.parent
        before_files = set(repo_root.iterdir())

        stub_report = {
            "schema_version": "diagnose_v1",
            "summary": {
                "tickers_with_eval": 1,
                "tickers_skipped": 0,
                "overall_score_pct": 100.0,
                "total_matched": 1,
                "total_expected": 1,
                "total_wrong": 0,
                "total_missed": 0,
                "total_extra": 0,
            },
            "hotspots": [],
            "by_field_category": {},
            "cases": [],
        }

        args = _make_args(output=None)
        with patch("elsian.diagnose.engine.build_report", return_value=stub_report):
            cmd_diagnose(args)

        after_files = set(repo_root.iterdir())
        new_files = after_files - before_files
        repo_relative_new = [f.name for f in new_files]
        assert "diagnose_report.json" not in repo_relative_new, (
            "diagnose_report.json must NOT be written to the repo root when "
            "--output is omitted"
        )
        assert "diagnose_report.md" not in repo_relative_new, (
            "diagnose_report.md must NOT be written to the repo root when "
            "--output is omitted"
        )


class TestDiagnoseAll:
    """Integration tests for cmd_diagnose with existing artifacts.

    All methods share a single ``cmd_diagnose`` run via the module-scoped
    ``shared_diagnose_result`` fixture, except ``test_does_not_mutate_case_artifacts``
    which requires its own isolated invocation to compare pre/post mtimes.
    """

    def test_cmd_diagnose_all_creates_json_and_md(
        self, shared_diagnose_result: tuple  # (Path, dict)
    ) -> None:
        """cmd_diagnose writes diagnose_report.json and diagnose_report.md."""
        out, _ = shared_diagnose_result
        assert (out / "diagnose_report.json").exists(), "diagnose_report.json not written"
        assert (out / "diagnose_report.md").exists(), "diagnose_report.md not written"

    def test_json_report_schema_version(
        self, shared_diagnose_result: tuple
    ) -> None:
        """diagnose_report.json has schema_version = diagnose_v1."""
        _, data = shared_diagnose_result
        assert data["schema_version"] == "diagnose_v1"

    def test_json_report_required_keys(
        self, shared_diagnose_result: tuple
    ) -> None:
        """diagnose_report.json contains all required top-level keys."""
        _, data = shared_diagnose_result
        for key in ("schema_version", "generated_at", "summary", "hotspots",
                    "by_ticker", "by_source_hint",
                    "by_period_type", "by_field_category", "root_cause_summary"):
            assert key in data, f"Missing top-level key: {key}"

    def test_hotspots_have_root_cause_hint_and_field_category(
        self, shared_diagnose_result: tuple
    ) -> None:
        """Each hotspot in the JSON report has root_cause_hint and field_category fields."""
        _, data = shared_diagnose_result
        for h in data.get("hotspots", []):
            assert "root_cause_hint" in h, f"Hotspot missing root_cause_hint: {h}"
            assert "field_category" in h, f"Hotspot missing field_category: {h}"
            assert isinstance(h["root_cause_hint"], str) and h["root_cause_hint"]
            assert isinstance(h["field_category"], str) and h["field_category"]

    def test_by_period_type_is_dict(
        self, shared_diagnose_result: tuple
    ) -> None:
        """by_period_type is a dict (possibly empty) in the JSON report."""
        _, data = shared_diagnose_result
        assert isinstance(data["by_period_type"], dict)

    def test_by_field_category_is_dict(
        self, shared_diagnose_result: tuple
    ) -> None:
        """by_field_category is a dict in the JSON report."""
        _, data = shared_diagnose_result
        assert isinstance(data["by_field_category"], dict)

    def test_markdown_contains_new_sections(
        self, shared_diagnose_result: tuple
    ) -> None:
        """diagnose_report.md contains the Slice-2 sections when hotspots are present.

        "Root Cause Hint" and related grouping sections are only rendered when
        the report has at least one hotspot (wrong/missed field).  When the
        baseline is 100%, there are no hotspots and those sections are omitted.
        """
        out, data = shared_diagnose_result
        md = (out / "diagnose_report.md").read_text(encoding="utf-8")
        if data.get("hotspots"):
            assert "Root Cause Hint" in md
            assert "By Period Type" in md
            assert "By Field Category" in md
        else:
            # At 100% score there are no hotspots; verify the header sections still exist
            assert "## Summary" in md
            assert "## Per-Ticker Summary" in md

    def test_summary_counts_are_consistent(
        self, shared_diagnose_result: tuple
    ) -> None:
        """tickers_with_eval + tickers_skipped == tickers_analyzed."""
        _, data = shared_diagnose_result
        s = data["summary"]
        assert s["tickers_with_eval"] + s["tickers_skipped"] == s["tickers_analyzed"]

    def test_hotspots_have_required_fields(
        self, shared_diagnose_result: tuple
    ) -> None:
        """Each hotspot entry has required keys."""
        _, data = shared_diagnose_result
        for h in data.get("hotspots", []):
            for key in ("rank", "field", "gap_type", "occurrences",
                        "affected_tickers", "evidence"):
                assert key in h, f"Hotspot missing key: {key}"

    def test_hotspots_ranked_monotonically(
        self, shared_diagnose_result: tuple
    ) -> None:
        """Hotspot ranks are 1, 2, 3, … without gaps."""
        _, data = shared_diagnose_result
        hotspots = data.get("hotspots", [])
        for i, h in enumerate(hotspots, start=1):
            assert h["rank"] == i

    def test_hotspots_occurrences_non_increasing(
        self, shared_diagnose_result: tuple
    ) -> None:
        """Hotspot list is sorted by occurrences descending."""
        _, data = shared_diagnose_result
        hotspots = data.get("hotspots", [])
        for i in range(len(hotspots) - 1):
            assert hotspots[i]["occurrences"] >= hotspots[i + 1]["occurrences"]

    def test_md_report_contains_summary_and_hotspots(
        self, shared_diagnose_result: tuple
    ) -> None:
        """diagnose_report.md contains Summary and Hotspot sections."""
        out, _ = shared_diagnose_result
        md = (out / "diagnose_report.md").read_text(encoding="utf-8")
        assert "# ELSIAN Diagnose Report" in md
        assert "## Summary" in md

    def test_by_ticker_entries_have_all_keys(
        self, shared_diagnose_result: tuple
    ) -> None:
        """Each by_ticker entry has required keys."""
        _, data = shared_diagnose_result
        for ticker, d in data.get("by_ticker", {}).items():
            for key in ("score", "matched", "total_expected", "wrong",
                        "missed", "extra", "source_hint", "skipped"):
                assert key in d, f"{ticker} missing key: {key}"

    @pytest.mark.skipif(
        not _has_any_evaluable_case(),
        reason="No evaluable cases (expected.json + filings) found",
    )
    def test_does_not_mutate_case_artifacts(
        self,
        _case_mtimes_before: dict,
        shared_diagnose_result: tuple,  # ensures cmd_diagnose has already run
    ) -> None:
        """cmd_diagnose does not write to cases/ ground-truth files.

        Uses the pre-cmd_diagnose mtime snapshot from ``_case_mtimes_before``.
        Only ``expected.json`` and ``case.json`` are checked — both are
        curator-controlled ground truth that must never be overwritten.
        ``extraction_result.json`` is legitimately refreshed by the extract
        phase when diagnose re-extracts on-the-fly (BL-069 fix).
        """
        _PROTECTED = {"expected.json", "case.json"}
        for path_str, mtime_before in _case_mtimes_before.items():
            if Path(path_str).name not in _PROTECTED:
                continue
            mtime_after = Path(path_str).stat().st_mtime
            assert mtime_after == mtime_before, f"Ground-truth file was mutated: {path_str}"


# ── Engine-level integration ──────────────────────────────────────────


class TestDiagnoseEngine:
    """Integration tests for the engine build_report function directly.

    Uses the module-scoped ``engine_report`` fixture to avoid calling
    build_report more than once across test methods.
    """

    def test_build_report_on_real_cases_dir(self, engine_report: dict) -> None:
        """build_report on the real CASES_DIR returns a valid report."""
        assert engine_report["schema_version"] == "diagnose_v1"
        assert engine_report["summary"]["tickers_analyzed"] > 0
        assert isinstance(engine_report["hotspots"], list)

    def test_gap_type_values_are_valid(self, engine_report: dict) -> None:
        """All hotspot gap_type values are 'wrong' or 'missed'."""
        valid = {"wrong", "missed"}
        for h in engine_report["hotspots"]:
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
    def test_diagnose_report_tickers_with_eval_never_skipped(
        self, engine_report: dict
    ) -> None:
        """build_report on real cases must report tickers_skipped == 0.

        After the fix, every case with expected.json is evaluated on-the-fly;
        none should be counted as skipped.
        """
        assert engine_report["summary"]["tickers_skipped"] == 0, (
            f"Expected 0 skipped tickers but got {engine_report['summary']['tickers_skipped']}; "
            "diagnose may still be reading stale artifacts for some cases"
        )

    @pytest.mark.skipif(not _tzoo_evaluable(), reason="TZOO expected.json or filings missing")
    def test_diagnose_all_tickers_100pct_when_eval_all_pass(
        self, engine_report: dict
    ) -> None:
        """When eval --all is 100%, build_report overall_score_pct must also be 100%.

        This is the direct reproduction of the BL-069 auditor's blocker:
        diagnose reported 99.2% (ADTN with 37 wrong from stale artifact)
        while eval --all reported 17/17 PASS 100%.
        """
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

        # Verify diagnose agrees (engine_report already built once by the fixture)
        assert engine_report["summary"]["overall_score_pct"] == 100.0, (
            f"eval --all is 100% but diagnose reports "
            f"{engine_report['summary']['overall_score_pct']:.2f}%; stale artifact divergence"
        )
