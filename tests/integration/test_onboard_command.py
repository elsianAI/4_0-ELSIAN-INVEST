"""tests/integration/test_onboard_command.py — integration tests for `elsian onboard`.

All tests are deliberately offline — they use existing cases/ dirs
(TZOO, KAR) that already have filings/ populated locally.
No network calls are made (with_acquire=False by default).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

CASES_DIR = Path(__file__).resolve().parent.parent.parent / "cases"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _has_filings(ticker: str) -> bool:
    d = CASES_DIR / ticker / "filings"
    return d.exists() and any(d.iterdir())


def _has_case_json(ticker: str) -> bool:
    return (CASES_DIR / ticker / "case.json").exists()


def _make_onboard_args(**kwargs: Any) -> argparse.Namespace:
    defaults: dict[str, Any] = {
        "ticker": "TZOO",
        "with_acquire": False,
        "force": False,
        "allow_network_discover": False,
        "workspace": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ── run_onboarding public API ─────────────────────────────────────────


class TestRunOnboardingRealCases:
    """Uses real cases/ dirs — offline, no acquire."""

    @pytest.mark.skipif(
        not _has_case_json("TZOO"), reason="TZOO case.json not present"
    )
    def test_tzoo_returns_ok_or_warning(self) -> None:
        from elsian.onboarding import run_onboarding

        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO")
        assert report["original_ticker"] == "TZOO"
        assert report["summary"]["overall_status"] in ("ok", "warning")
        assert "discover" in report["steps"]

    @pytest.mark.skipif(
        not _has_case_json("TZOO"), reason="TZOO case.json not present"
    )
    def test_tzoo_discover_ok(self) -> None:
        from elsian.onboarding import run_onboarding

        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO")
        assert report["steps"]["discover"]["status"] == "ok"
        assert report["steps"]["discover"]["evidence"]["reused_existing_case"] is True

    @pytest.mark.skipif(
        not _has_case_json("TZOO"), reason="TZOO case.json not present"
    )
    def test_tzoo_no_acquire_step(self) -> None:
        from elsian.onboarding import run_onboarding

        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO", with_acquire=False)
        assert "acquire" not in report["steps"]

    @pytest.mark.skipif(
        not _has_case_json("TZOO") or not _has_filings("TZOO"),
        reason="TZOO filings not present",
    )
    def test_tzoo_convert_and_preflight(self) -> None:
        from elsian.onboarding import run_onboarding

        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO")
        assert "convert" in report["steps"]
        assert "preflight" in report["steps"]
        assert report["steps"]["convert"]["status"] in ("ok", "warning", "skipped")

    @pytest.mark.skipif(
        not _has_case_json("KAR"), reason="KAR case.json not present"
    )
    def test_kar_returns_ok_or_warning(self) -> None:
        from elsian.onboarding import run_onboarding

        report = run_onboarding("KAR", case_dir=CASES_DIR / "KAR")
        assert report["original_ticker"] == "KAR"
        assert report["summary"]["overall_status"] in ("ok", "warning", "skipped")

    def test_unknown_ticker_returns_discover_skipped(self, tmp_path: Path) -> None:
        from elsian.onboarding import run_onboarding

        report = run_onboarding("ZJUNK99", case_dir=tmp_path / "ZJUNK99")
        assert report["steps"]["discover"]["status"] in ("skipped", "fatal")
        assert set(report["steps"].keys()) == {"discover"}

    def test_report_keys_complete(self) -> None:
        from elsian.onboarding import run_onboarding

        if not _has_case_json("TZOO"):
            pytest.skip("TZOO not available")
        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO")
        for key in ("original_ticker", "canonical_ticker", "case_dir", "steps", "summary"):
            assert key in report, f"Missing key: {key}"
        for key in ("overall_status", "blockers", "warnings", "next_step"):
            assert key in report["summary"], f"Missing summary key: {key}"

    def test_report_blockers_is_list(self) -> None:
        from elsian.onboarding import run_onboarding

        if not _has_case_json("TZOO"):
            pytest.skip("TZOO not available")
        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO")
        assert isinstance(report["summary"]["blockers"], list)
        assert isinstance(report["summary"]["warnings"], list)

    def test_steps_statuses_are_valid(self) -> None:
        from elsian.onboarding import run_onboarding

        if not _has_case_json("TZOO"):
            pytest.skip("TZOO not available")
        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO")
        valid = {"ok", "warning", "fatal", "skipped"}
        for step_name, step in report["steps"].items():
            assert step["status"] in valid, f"Step {step_name} has invalid status: {step['status']}"


# ── workspace output ──────────────────────────────────────────────────


class TestWorkspaceOutput:
    """Tests that --workspace writes the expected files."""

    @pytest.mark.skipif(
        not _has_case_json("TZOO"), reason="TZOO case.json not present"
    )
    def test_workspace_writes_json(self, tmp_path: Path) -> None:
        from elsian.onboarding import run_onboarding
        import json as _json

        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO")
        out_dir = tmp_path / "TZOO"
        out_dir.mkdir()
        (out_dir / "onboarding_report.json").write_text(
            _json.dumps(report, indent=2), encoding="utf-8"
        )
        written = _json.loads((out_dir / "onboarding_report.json").read_text())
        assert written["original_ticker"] == "TZOO"

    @pytest.mark.skipif(
        not _has_case_json("TZOO"), reason="TZOO case.json not present"
    )
    def test_workspace_writes_md(self, tmp_path: Path) -> None:
        from elsian.onboarding import run_onboarding, render_report_md

        report = run_onboarding("TZOO", case_dir=CASES_DIR / "TZOO")
        md = render_report_md(report)
        out_dir = tmp_path / "TZOO"
        out_dir.mkdir()
        (out_dir / "onboarding_report.md").write_text(md, encoding="utf-8")
        content = (out_dir / "onboarding_report.md").read_text()
        assert "TZOO" in content
        assert "#" in content  # has at least one Markdown heading


# ── cmd_onboard CLI wrapper ───────────────────────────────────────────


class TestCmdOnboard:
    """Tests for the cmd_onboard CLI function."""

    @pytest.mark.skipif(
        not _has_case_json("TZOO"), reason="TZOO case.json not present"
    )
    def test_cmd_onboard_tzoo_exits_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        from elsian.cli import cmd_onboard

        args = _make_onboard_args(ticker="TZOO", workspace=None)
        # monkeypatch _find_case_dir to return real TZOO dir
        import elsian.cli as cli_module

        original = cli_module._find_case_dir

        def patched(ticker: str) -> Path | None:
            if ticker.upper() == "TZOO":
                return CASES_DIR / "TZOO"
            return original(ticker)

        cli_module._find_case_dir = patched
        try:
            cmd_onboard(args)  # must not raise or sys.exit
        finally:
            cli_module._find_case_dir = original

        captured = capsys.readouterr()
        assert "TZOO" in captured.out or "onboarding" in captured.out.lower()

    def test_cmd_onboard_missing_ticker_does_not_crash(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        from elsian.cli import cmd_onboard

        args = _make_onboard_args(ticker="ZJUNK99", workspace=None)
        # Should complete normally (discover=skipped, not fatal enough for sys.exit)
        # If it exits 1 (fatal), that's also acceptable; we just don't want a traceback
        try:
            cmd_onboard(args)
        except SystemExit as exc:
            assert exc.code in (0, 1)

    @pytest.mark.skipif(
        not _has_case_json("TZOO"), reason="TZOO case.json not present"
    )
    def test_cmd_onboard_workspace_creates_files(
        self, tmp_path: Path
    ) -> None:
        from elsian.cli import cmd_onboard
        import elsian.cli as cli_module

        workspace = tmp_path / "ws"
        workspace.mkdir()
        args = _make_onboard_args(ticker="TZOO", workspace=str(workspace))

        original = cli_module._find_case_dir

        def patched(ticker: str) -> Path | None:
            if ticker.upper() == "TZOO":
                return CASES_DIR / "TZOO"
            return original(ticker)

        cli_module._find_case_dir = patched
        try:
            cmd_onboard(args)
        finally:
            cli_module._find_case_dir = original

        out_dir = workspace / "TZOO"
        assert out_dir.exists()
        assert (out_dir / "onboarding_report.json").exists()
        assert (out_dir / "onboarding_report.md").exists()


# ── Audit blocker regression tests ───────────────────────────────────


class TestAuditBlockerRegressionsIntegration:
    """Integration-level regression tests for BL-067 audit blockers.

    These tests exercise cmd_onboard (the CLI entrypoint) rather than
    run_onboarding directly, to confirm the full stack handles the blocker
    scenarios gracefully.
    """

    def test_corrupt_case_json_exits_1_no_traceback(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """cmd_onboard with a corrupt case.json must exit(1), not raise."""
        from elsian.cli import cmd_onboard

        corrupt_dir = tmp_path / "CORRUPT"
        corrupt_dir.mkdir()
        (corrupt_dir / "case.json").write_bytes(b"{ NOT VALID JSON !!!")

        args = _make_onboard_args(ticker="CORRUPT", workspace=None)

        import elsian.cli as cli_module

        original = cli_module._find_case_dir

        def patched(ticker: str) -> Path | None:
            if ticker.upper() == "CORRUPT":
                return corrupt_dir
            return original(ticker)

        cli_module._find_case_dir = patched
        try:
            with pytest.raises(SystemExit) as exc_info:
                cmd_onboard(args)
        finally:
            cli_module._find_case_dir = original

        # Must exit with code 1 (fatal), not propagate a JSONDecodeError.
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        # Output must mention BLOCKER or fatal — no raw Python traceback.
        assert "BLOCKER" in captured.out or "FATAL" in captured.out or "fatal" in captured.out
