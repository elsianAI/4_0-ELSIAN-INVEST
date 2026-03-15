"""tests/unit/test_onboarding.py — unit tests for elsian.onboarding.

Tests _step_result, _classify_overall, and individual step runners
using tmp_path fixtures — no network, no real case dirs required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from elsian.onboarding import (
    _classify_overall,
    _run_convert_step,
    _run_discover_step,
    _run_preflight_step,
    _step_result,
    render_report_md,
    run_onboarding,
)


# ── _step_result ──────────────────────────────────────────────────────


class TestStepResult:
    def test_minimal(self) -> None:
        r = _step_result("ok")
        assert r == {"status": "ok"}

    def test_with_evidence(self) -> None:
        r = _step_result("warning", evidence={"x": 1})
        assert r["status"] == "warning"
        assert r["evidence"] == {"x": 1}
        assert "gaps" not in r

    def test_with_gaps(self) -> None:
        r = _step_result("warning", gaps=["problem A"])
        assert r["gaps"] == ["problem A"]

    def test_with_next_step_override(self) -> None:
        r = _step_result("skipped", next_step_override="do something")
        assert r["next_step_override"] == "do something"

    def test_empty_evidence_omitted(self) -> None:
        r = _step_result("ok", evidence=None, gaps=None)
        assert "evidence" not in r
        assert "gaps" not in r


# ── _classify_overall ─────────────────────────────────────────────────


class TestClassifyOverall:
    def test_all_ok(self) -> None:
        steps = {
            "discover": _step_result("ok"),
            "convert": _step_result("ok"),
        }
        overall, blockers, warnings, next_step = _classify_overall(steps)
        assert overall == "ok"
        assert blockers == []
        assert warnings == []
        assert "expected_draft" in next_step.lower() or "promote" in next_step.lower()

    def test_fatal_dominates(self) -> None:
        steps = {
            "discover": _step_result("ok"),
            "convert": _step_result("fatal", evidence={"error": "disk full"}),
        }
        overall, blockers, warnings, _ = _classify_overall(steps)
        assert overall == "fatal"
        assert any("disk full" in b for b in blockers)

    def test_warning_propagates(self) -> None:
        steps = {
            "discover": _step_result("ok"),
            "convert": _step_result("warning", gaps=["3 filings failed"]),
        }
        overall, blockers, warnings, _ = _classify_overall(steps)
        assert overall == "warning"
        assert blockers == []
        assert any("3 filings failed" in w for w in warnings)

    def test_skipped_only_is_ok(self) -> None:
        steps = {
            "discover": _step_result("skipped"),
        }
        overall, _, _, _ = _classify_overall(steps)
        # All skipped → skipped (no "ok" in statuses)
        assert overall == "skipped"

    def test_ok_and_skipped(self) -> None:
        steps = {
            "discover": _step_result("ok"),
            "acquire": _step_result("skipped"),
        }
        overall, _, _, _ = _classify_overall(steps)
        assert overall == "ok"

    def test_fatal_gap_goes_to_blockers(self) -> None:
        steps = {
            "convert": _step_result("fatal", gaps=["all failed"], evidence={"error": "boom"}),
        }
        _, blockers, warnings, _ = _classify_overall(steps)
        assert any("all failed" in b for b in blockers)
        assert warnings == []

    def test_next_step_discover_skipped(self) -> None:
        steps = {"discover": _step_result("skipped")}
        _, _, _, next_step = _classify_overall(steps)
        assert "discover" in next_step.lower() or "case.json" in next_step.lower()

    def test_next_step_acquire_fatal(self) -> None:
        steps = {
            "discover": _step_result("ok"),
            "acquire": _step_result("fatal", evidence={"error": "timeout"}),
        }
        _, _, _, next_step = _classify_overall(steps)
        assert "acquire" in next_step.lower()

    def test_next_step_convert_warning(self) -> None:
        steps = {
            "discover": _step_result("ok"),
            "convert": _step_result("warning", gaps=["1 filing failed"]),
        }
        _, _, _, next_step = _classify_overall(steps)
        assert "convert" in next_step.lower() or "force" in next_step.lower()


# ── _run_discover_step ────────────────────────────────────────────────


class TestRunDiscoverStep:
    def test_reuses_existing_case(self, tmp_path: Path) -> None:
        case = {
            "ticker": "TEST",
            "source_hint": "sec",
            "currency": "USD",
            "period_scope": "FULL",
        }
        (tmp_path / "case.json").write_text(
            json.dumps(case), encoding="utf-8"
        )
        result = _run_discover_step("TEST", tmp_path, allow_network=False)
        assert result["status"] == "ok"
        assert result["evidence"]["reused_existing_case"] is True
        assert result["evidence"]["source_hint"] == "sec"

    def test_skips_when_no_case_no_network(self, tmp_path: Path) -> None:
        result = _run_discover_step("NOTEXIST", tmp_path, allow_network=False)
        assert result["status"] == "skipped"
        assert result["gaps"]
        assert result.get("next_step_override")

    def test_fatal_on_unreadable_case(self, tmp_path: Path) -> None:
        (tmp_path / "case.json").write_bytes(b"\xff\xfe invalid json")
        result = _run_discover_step("TEST", tmp_path, allow_network=False)
        assert result["status"] == "fatal"
        assert result["gaps"]

    def test_network_discover_writes_to_case_dir_not_global_cases(
        self, tmp_path: Path
    ) -> None:
        """When allow_network=True and TickerDiscoverer succeeds, case.json is
        written to the *case_dir* parameter, not to any hardcoded CASES_DIR path.
        """
        from unittest.mock import MagicMock, patch

        mock_result = MagicMock()
        mock_result.source_hint = "sec"
        mock_result.exchange = "NYSE"
        mock_result.currency = "USD"
        mock_result.period_scope = "FULL"
        mock_result.warnings = []
        mock_result.to_case_dict.return_value = {
            "ticker": "FAKE",
            "source_hint": "sec",
            "currency": "USD",
        }

        mock_discoverer = MagicMock()
        mock_discoverer.discover.return_value = mock_result

        custom_case_dir = tmp_path / "custom_subdir"
        custom_case_dir.mkdir()

        with patch("elsian.discover.discover.TickerDiscoverer", return_value=mock_discoverer), \
             patch("elsian.onboarding.CASES_DIR", tmp_path / "should_not_write_here"):
            result = _run_discover_step("FAKE", custom_case_dir, allow_network=True)

        # case.json must land in custom_case_dir, not in any CASES_DIR subpath
        assert (custom_case_dir / "case.json").exists(), (
            "case.json must be written to the case_dir parameter"
        )
        # The hardcoded fallback path must NOT be written
        wrong_path = tmp_path / "should_not_write_here" / "FAKE" / "case.json"
        assert not wrong_path.exists(), (
            "case.json must NOT be written to CASES_DIR / ticker"
        )
        assert result["status"] in ("ok", "warning")


# ── _run_convert_step ─────────────────────────────────────────────────


class TestRunConvertStep:
    def test_no_filings_dir(self, tmp_path: Path) -> None:
        result = _run_convert_step(tmp_path)
        assert result["status"] == "skipped"
        assert result["gaps"]

    def test_empty_filings_dir(self, tmp_path: Path) -> None:
        (tmp_path / "filings").mkdir()
        result = _run_convert_step(tmp_path)
        assert result["status"] == "skipped"
        assert result["evidence"]["total"] == 0

    def test_skips_existing_clean_md(self, tmp_path: Path) -> None:
        filings = tmp_path / "filings"
        filings.mkdir()
        (filings / "SRC_001.htm").write_text(
            "<html><body><p>hello</p></body></html>", encoding="utf-8"
        )
        (filings / "SRC_001.clean.md").write_text("# existing", encoding="utf-8")
        result = _run_convert_step(tmp_path, force=False)
        assert result["status"] == "ok"
        assert result["evidence"]["skipped"] == 1
        assert result["evidence"]["converted"] == 0
        # Existing clean.md must not be overwritten
        assert (filings / "SRC_001.clean.md").read_text() == "# existing"

    def test_force_reconverts(self, tmp_path: Path) -> None:
        filings = tmp_path / "filings"
        filings.mkdir()
        (filings / "SRC_001.htm").write_text(
            "<html><body><p>data</p></body></html>", encoding="utf-8"
        )
        (filings / "SRC_001.clean.md").write_text("# old", encoding="utf-8")
        result = _run_convert_step(tmp_path, force=True)
        assert result["evidence"]["total"] == 1
        # Either converted or skipped (empty output); no failure
        assert result["evidence"]["failed"] == 0


# ── _run_preflight_step ───────────────────────────────────────────────


class TestRunPreflightStep:
    def test_no_filings_dir(self, tmp_path: Path) -> None:
        result = _run_preflight_step(tmp_path)
        assert result["status"] == "skipped"

    def test_no_converted(self, tmp_path: Path) -> None:
        (tmp_path / "filings").mkdir()
        result = _run_preflight_step(tmp_path)
        assert result["status"] == "skipped"
        assert result["gaps"]

    def test_with_us_gaap_text(self, tmp_path: Path) -> None:
        filings = tmp_path / "filings"
        filings.mkdir()
        us_text = (
            "Consolidated Statements of Operations\n"
            "(in thousands)\n"
            "Year Ended December 31, 2024\n"
            "Net revenues: $83,902\n"
            "Total assets: 180,000\n"
            "The financial statements have been prepared in accordance with U.S. GAAP.\n"
            "United States dollars (USD).\n"
        )
        (filings / "SRC_001.clean.md").write_text(us_text, encoding="utf-8")
        result = _run_preflight_step(tmp_path)
        assert result["status"] == "ok"
        ev = result["evidence"]
        assert ev.get("accounting_standard") == "US-GAAP"
        assert ev.get("currency") == "USD"
        assert ev.get("sampled_file") == "SRC_001.clean.md"
        assert ev.get("total_converted") == 1


# ── render_report_md ──────────────────────────────────────────────────


class TestRenderReportMd:
    def _make_report(self) -> dict:
        return {
            "original_ticker": "TZOO",
            "canonical_ticker": "TZOO",
            "case_dir": "/cases/TZOO",
            "steps": {
                "discover": _step_result("ok", evidence={"reused_existing_case": True}),
                "convert": _step_result("warning", gaps=["1 filing failed"]),
            },
            "summary": {
                "overall_status": "warning",
                "blockers": [],
                "warnings": ["convert: 1 filing failed"],
                "next_step": "Re-run with --force",
            },
        }

    def test_contains_ticker(self) -> None:
        md = render_report_md(self._make_report())
        assert "TZOO" in md

    def test_contains_status(self) -> None:
        md = render_report_md(self._make_report())
        assert "WARNING" in md

    def test_contains_steps(self) -> None:
        md = render_report_md(self._make_report())
        assert "discover" in md
        assert "convert" in md

    def test_contains_next_step(self) -> None:
        md = render_report_md(self._make_report())
        assert "--force" in md


# ── run_onboarding smoke (no-network, existing case) ─────────────────


class TestRunOnboardingSmoke:
    """Smoke tests using a minimal synthetic case dir — no network."""

    def _make_case(self, tmp_path: Path) -> Path:
        case = {
            "ticker": "TEST",
            "source_hint": "sec",
            "currency": "USD",
            "period_scope": "FULL",
        }
        (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
        filings = tmp_path / "filings"
        filings.mkdir()
        # One pre-converted filing so convert/preflight/draft can run
        (filings / "SRC_001.clean.md").write_text(
            "Total assets: 1000\nNet income: 100\nin thousands\nU.S. GAAP\nUSD\n"
            "Year Ended December 31, 2024\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_report_structure(self, tmp_path: Path) -> None:
        case_dir = self._make_case(tmp_path)
        report = run_onboarding("TEST", case_dir=case_dir)
        assert "original_ticker" in report
        assert "canonical_ticker" in report
        assert "case_dir" in report
        assert "steps" in report
        assert "summary" in report
        assert "overall_status" in report["summary"]
        assert "blockers" in report["summary"]
        assert "warnings" in report["summary"]
        assert "next_step" in report["summary"]

    def test_discover_step_present(self, tmp_path: Path) -> None:
        case_dir = self._make_case(tmp_path)
        report = run_onboarding("TEST", case_dir=case_dir)
        assert "discover" in report["steps"]
        assert report["steps"]["discover"]["status"] == "ok"

    def test_convert_step_present(self, tmp_path: Path) -> None:
        case_dir = self._make_case(tmp_path)
        report = run_onboarding("TEST", case_dir=case_dir)
        assert "convert" in report["steps"]
        # All clean.md already exist → skipped
        assert report["steps"]["convert"]["status"] in ("ok", "skipped")

    def test_preflight_step_present(self, tmp_path: Path) -> None:
        case_dir = self._make_case(tmp_path)
        report = run_onboarding("TEST", case_dir=case_dir)
        assert "preflight" in report["steps"]

    def test_draft_step_present(self, tmp_path: Path) -> None:
        case_dir = self._make_case(tmp_path)
        report = run_onboarding("TEST", case_dir=case_dir)
        assert "draft" in report["steps"]

    def test_no_acquire_step_by_default(self, tmp_path: Path) -> None:
        case_dir = self._make_case(tmp_path)
        report = run_onboarding("TEST", case_dir=case_dir, with_acquire=False)
        assert "acquire" not in report["steps"]

    def test_missing_case_json_returns_early(self, tmp_path: Path) -> None:
        report = run_onboarding("MISSING", case_dir=tmp_path)
        # discover must be skipped; no other steps
        assert "discover" in report["steps"]
        assert set(report["steps"].keys()) == {"discover"}
        assert report["summary"]["overall_status"] in ("skipped", "fatal")

    def test_canonical_ticker_from_case(self, tmp_path: Path) -> None:
        case_dir = self._make_case(tmp_path)
        report = run_onboarding("test", case_dir=case_dir)
        # CaseConfig.ticker is "TEST"; must be used as canonical
        assert report["canonical_ticker"] == "TEST"


# ── Audit blocker regression tests ───────────────────────────────────


class TestAuditBlockerRegressions:
    """Regression tests for BL-067 audit blockers.

    Blocker 1: corrupt case.json must return a fatal report, not traceback.
    Blocker 2: fatal convert must stop the flow; preflight/draft must not run.
    """

    def test_corrupt_case_json_returns_fatal_no_traceback(self, tmp_path: Path) -> None:
        """Corrupt case.json: run_onboarding must return a fatal report, not raise."""
        (tmp_path / "case.json").write_bytes(b"{ NOT VALID JSON !!!")
        # Must not raise; must return a structured fatal report.
        report = run_onboarding("TEST", case_dir=tmp_path)
        assert report["summary"]["overall_status"] == "fatal"
        assert report["steps"]["discover"]["status"] == "fatal"
        # Only discover step should be present — no further steps should run.
        assert set(report["steps"].keys()) == {"discover"}
        # Blockers must mention the failure.
        assert report["summary"]["blockers"]

    def test_corrupt_case_json_blockers_mention_error(self, tmp_path: Path) -> None:
        """Blockers list must reference the corrupt-file error."""
        (tmp_path / "case.json").write_bytes(b"\xff\xfe not json")
        report = run_onboarding("TEST", case_dir=tmp_path)
        blockers_text = " ".join(report["summary"]["blockers"])
        # Must mention something about the error (case.json / unreadable / parse).
        assert any(
            kw in blockers_text.lower()
            for kw in ("case.json", "unreadable", "parse", "error", "cannot")
        )

    def test_fatal_convert_stops_before_preflight_and_draft(self, tmp_path: Path) -> None:
        """If all filings fail to convert, preflight and draft must not run."""
        # Set up a valid case.json.
        case = {
            "ticker": "TEST",
            "source_hint": "sec",
            "currency": "USD",
            "period_scope": "FULL",
        }
        (tmp_path / "case.json").write_text(
            __import__("json").dumps(case), encoding="utf-8"
        )
        # Set up a filings dir with one .htm that will fail to convert (binary garbage).
        filings = tmp_path / "filings"
        filings.mkdir()
        (filings / "SRC_001.htm").write_bytes(b"\x00" * 100)  # binary, not HTML
        # Do NOT pre-create a .clean.md so convert must attempt and fail.

        # Patch the html converter to always raise so convert→fatal is deterministic.
        import elsian.onboarding as onb_module
        import elsian.convert.html_to_markdown as html_mod

        original_convert = html_mod.convert

        def always_fail(path):  # type: ignore[override]
            raise RuntimeError("simulated convert failure")

        html_mod.convert = always_fail
        try:
            report = run_onboarding("TEST", case_dir=tmp_path)
        finally:
            html_mod.convert = original_convert

        assert report["steps"]["convert"]["status"] == "fatal"
        assert "preflight" not in report["steps"], (
            "preflight must not run when convert is fatal"
        )
        assert "draft" not in report["steps"], (
            "draft must not run when convert is fatal"
        )
        assert report["summary"]["overall_status"] == "fatal"
