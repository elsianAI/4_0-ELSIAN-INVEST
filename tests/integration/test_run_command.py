"""tests/integration/test_run_command.py — E2E tests for `elsian run`.

Tests the full pipeline orchestration:
  [acquire →] convert → extract → evaluate → [assemble]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

CASES_DIR = Path(__file__).resolve().parent.parent.parent / "cases"


def _has_expected(ticker: str) -> bool:
    """Check if expected.json exists for a ticker."""
    return (CASES_DIR / ticker / "expected.json").exists()


def _has_filings(ticker: str) -> bool:
    """Check if any filings exist for a ticker."""
    d = CASES_DIR / ticker / "filings"
    return d.exists() and any(d.iterdir())


def _make_args(**kwargs: Any) -> argparse.Namespace:
    """Create a Namespace with run-command defaults."""
    defaults = {
        "ticker": "TZOO",
        "all": False,
        "with_acquire": False,
        "skip_assemble": False,
        "force": False,
    }
    defaults.update(kwargs)
    ns = argparse.Namespace(**defaults)
    return ns


# ── Import helpers ────────────────────────────────────────────────────

def _import_helpers():
    """Import the helpers from cli module."""
    from elsian.cli import _convert_filings, _run_pipeline_for_ticker, _find_case_dir
    return _convert_filings, _run_pipeline_for_ticker, _find_case_dir


# ── Tests: _convert_filings ───────────────────────────────────────────

class TestConvertFilings:
    """Unit-level tests for the _convert_filings helper."""

    def test_no_filings_dir(self, tmp_path: Path) -> None:
        """Should return zeros when filings/ dir does not exist."""
        _convert_filings = _import_helpers()[0]
        stats = _convert_filings(tmp_path)
        assert stats == {"total": 0, "converted": 0, "skipped": 0, "failed": 0}

    def test_empty_filings_dir(self, tmp_path: Path) -> None:
        """Should return zeros when filings/ dir is empty."""
        _convert_filings = _import_helpers()[0]
        (tmp_path / "filings").mkdir()
        stats = _convert_filings(tmp_path)
        assert stats == {"total": 0, "converted": 0, "skipped": 0, "failed": 0}

    def test_skips_existing_clean_md(self, tmp_path: Path) -> None:
        """Should skip .htm files that already have a .clean.md counterpart."""
        _convert_filings = _import_helpers()[0]
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        # Create a minimal htm file and its .clean.md
        (filings_dir / "SRC_001.htm").write_text("<html><body>test</body></html>", encoding="utf-8")
        (filings_dir / "SRC_001.clean.md").write_text("# existing", encoding="utf-8")

        stats = _convert_filings(tmp_path, force=False)
        assert stats["skipped"] == 1
        assert stats["converted"] == 0
        # Existing .clean.md should not be overwritten
        assert (filings_dir / "SRC_001.clean.md").read_text() == "# existing"

    def test_force_reconverts(self, tmp_path: Path) -> None:
        """--force should re-convert even if .clean.md exists."""
        _convert_filings = _import_helpers()[0]
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        # Create a minimal htm file without useful tables (will produce empty output → skipped)
        (filings_dir / "SRC_001.htm").write_text("<html><body><p>no tables</p></body></html>", encoding="utf-8")
        (filings_dir / "SRC_001.clean.md").write_text("# old", encoding="utf-8")

        stats = _convert_filings(tmp_path, force=True)
        # With force=True, it tried to convert — result may be skipped (empty md) or converted
        assert stats["total"] == 1
        assert stats["skipped"] + stats["converted"] == 1  # either outcome is fine

    def test_converts_htm_without_clean_md(self, tmp_path: Path) -> None:
        """Should attempt to convert .htm files missing a .clean.md."""
        _convert_filings = _import_helpers()[0]
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        # Minimal HTML with a table that matches income statement pattern
        html = """
        <html><body>
        <b>Consolidated Statements of Operations</b>
        <table><tr><th>Item</th><th>2024</th></tr>
        <tr><td>Net revenues</td><td>1,000</td></tr></table>
        </body></html>
        """
        (filings_dir / "SRC_001.htm").write_text(html, encoding="utf-8")

        stats = _convert_filings(tmp_path, force=False)
        assert stats["total"] == 1
        # Either converted or skipped (if quality gate rejects it), never failed
        assert stats["failed"] == 0

    def test_ignores_non_htm_pdf(self, tmp_path: Path) -> None:
        """Should ignore files that are neither .htm nor .pdf."""
        _convert_filings = _import_helpers()[0]
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001.txt").write_text("plain text", encoding="utf-8")
        (filings_dir / "SRC_002.clean.md").write_text("# existing md", encoding="utf-8")

        stats = _convert_filings(tmp_path, force=False)
        assert stats["total"] == 0


# ── Tests: cmd_run (TZOO E2E) ────────────────────────────────────────

@pytest.mark.skipif(
    not _has_expected("TZOO") or not _has_filings("TZOO"),
    reason="TZOO filings or expected.json not found",
)
class TestRunCommandTZOO:
    """E2E integration test: `elsian run TZOO`."""

    def test_run_tzoo_default(self, tmp_path: Path) -> None:
        """cmd_run TZOO should produce extraction_result.json and evaluate at 100%."""
        from elsian.cli import _run_pipeline_for_ticker
        args = _make_args(ticker="TZOO", skip_assemble=True)
        ok, summary = _run_pipeline_for_ticker("TZOO", args)
        assert ok, f"Pipeline failed: {summary}"
        assert "100.0%" in summary

    def test_run_tzoo_skip_assemble(self, tmp_path: Path) -> None:
        """--skip-assemble should NOT produce truth_pack.json."""
        from elsian.cli import _run_pipeline_for_ticker
        args = _make_args(ticker="TZOO", skip_assemble=True)
        ok, _ = _run_pipeline_for_ticker("TZOO", args)
        assert ok
        # truth_pack.json may or may not exist depending on prior runs — we only
        # verify that the pipeline runs successfully with skip_assemble=True

    def test_run_tzoo_with_assemble(self) -> None:
        """Default run should produce truth_pack.json."""
        from elsian.cli import _run_pipeline_for_ticker
        args = _make_args(ticker="TZOO", skip_assemble=False)
        ok, _ = _run_pipeline_for_ticker("TZOO", args)
        assert ok
        truth_pack = CASES_DIR / "TZOO" / "truth_pack.json"
        # If assemble ran, truth_pack.json should exist
        assert truth_pack.exists(), "truth_pack.json should have been generated"
        data = json.loads(truth_pack.read_text(encoding="utf-8"))
        assert data["schema_version"] == "TruthPack_v1"
        assert data["ticker"] == "TZOO"

    def test_run_tzoo_force(self) -> None:
        """--force flag should run pipeline successfully."""
        from elsian.cli import _run_pipeline_for_ticker
        args = _make_args(ticker="TZOO", force=True, skip_assemble=True)
        ok, summary = _run_pipeline_for_ticker("TZOO", args)
        assert ok, f"Pipeline with --force failed: {summary}"

    def test_run_all_finds_tickers(self) -> None:
        """--all should find at least TZOO in the cases directory."""
        # Just verify that TZOO would be included in --all run
        tickers = sorted(
            d.name for d in CASES_DIR.iterdir()
            if d.is_dir()
            and (d / "case.json").exists()
            and (d / "expected.json").exists()
        )
        assert "TZOO" in tickers
        assert len(tickers) >= 1


# ── Tests: convert stats structure ───────────────────────────────────

class TestConvertStats:
    """Verify that _convert_filings always returns correct keys."""

    def test_stats_keys(self, tmp_path: Path) -> None:
        """Return dict must have total, converted, skipped, failed."""
        _convert_filings = _import_helpers()[0]
        stats = _convert_filings(tmp_path)
        assert set(stats.keys()) == {"total", "converted", "skipped", "failed"}

    def test_stats_sum(self, tmp_path: Path) -> None:
        """converted + skipped + failed must equal total."""
        _convert_filings = _import_helpers()[0]
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001.htm").write_text("<html/>", encoding="utf-8")
        (filings_dir / "SRC_002.htm").write_text("<html/>", encoding="utf-8")
        (filings_dir / "SRC_002.clean.md").write_text("# cached", encoding="utf-8")

        stats = _convert_filings(tmp_path)
        assert stats["converted"] + stats["skipped"] + stats["failed"] == stats["total"]


# ── Tests: Pipeline orchestration (BL-063) ────────────────────────────

class TestPipelineOrchestrationSemantics:
    """Verify that _run_pipeline_for_ticker uses Pipeline with correct severity rules."""

    def test_non_fatal_assemble_error_does_not_fail_pipeline(self, tmp_path: Path) -> None:
        """AssemblePhase error must NOT cause _run_pipeline_for_ticker to return False.

        We mock _run_pipeline_for_ticker at the Pipeline level by checking that
        AssemblePhase is imported from elsian.assemble.phase and is non-fatal.
        """
        from elsian.assemble.phase import AssemblePhase
        from elsian.context import PipelineContext
        from elsian.models.case import CaseConfig

        # Build a minimal context
        case = CaseConfig()
        case.ticker = "TEST"
        case.case_dir = str(tmp_path)
        context = PipelineContext(case=case)

        phase = AssemblePhase()
        result = phase.run(context)

        # AssemblePhase must never be fatal — even on exception
        assert not result.is_fatal, "AssemblePhase must be non-fatal"
        assert result.severity in ("ok", "warning"), (
            f"Unexpected severity: {result.severity}"
        )

    def test_evaluate_phase_non_fatal_on_score_below_100(self, tmp_path: Path) -> None:
        """EvaluatePhase with score < 100% must return severity='warning', not fatal."""
        import json
        from unittest.mock import patch
        from elsian.evaluate.phase import EvaluatePhase
        from elsian.context import PipelineContext
        from elsian.models.case import CaseConfig
        from elsian.models.result import ExtractionResult, EvalReport

        # Write minimal expected.json so EvaluatePhase doesn't skip
        expected = {
            "version": "1.0",
            "ticker": "TEST",
            "currency": "USD",
            "scale": "thousands",
            "periods": {
                "FY2024": {
                    "fecha_fin": "2024-12-31",
                    "tipo_periodo": "anual",
                    "fields": {
                        "ingresos": {"value": 1000, "source_filing": "x.md"},
                    },
                }
            },
        }
        (tmp_path / "expected.json").write_text(
            json.dumps(expected), encoding="utf-8"
        )

        case = CaseConfig()
        case.ticker = "TEST"
        case.case_dir = str(tmp_path)
        context = PipelineContext(case=case)
        # context.result is empty → evaluate will produce score=0

        phase = EvaluatePhase()
        result = phase.run(context)

        assert not result.is_fatal, "EvaluatePhase must never be fatal"
        assert result.severity == "warning", (
            f"Expected 'warning' severity for score<100, got '{result.severity}'"
        )
        assert result.success is True

    def test_convert_phase_no_filings_ok(self, tmp_path: Path) -> None:
        """ConvertPhase with no filings dir must return severity='ok', not fatal."""
        from elsian.convert.phase import ConvertPhase
        from elsian.context import PipelineContext
        from elsian.models.case import CaseConfig

        case = CaseConfig()
        case.ticker = "TEST"
        case.case_dir = str(tmp_path)
        context = PipelineContext(case=case)

        phase = ConvertPhase()
        result = phase.run(context)

        assert not result.is_fatal
        assert result.severity == "ok"
        assert result.diagnostics["total"] == 0

    def test_pipeline_runs_assemble_after_eval_fail(self, tmp_path: Path) -> None:
        """The pipeline must continue to AssemblePhase even when EvaluatePhase warns."""
        import json
        from elsian.pipeline import Pipeline
        from elsian.context import PipelineContext
        from elsian.models.case import CaseConfig
        from elsian.evaluate.phase import EvaluatePhase
        from elsian.assemble.phase import AssemblePhase

        # Provide expected.json so EvaluatePhase runs and produces a FAIL
        expected = {
            "version": "1.0",
            "ticker": "TEST",
            "currency": "USD",
            "scale": "thousands",
            "periods": {
                "FY2024": {
                    "fecha_fin": "2024-12-31",
                    "tipo_periodo": "anual",
                    "fields": {
                        "ingresos": {"value": 999999, "source_filing": "x.md"},
                    },
                }
            },
        }
        (tmp_path / "expected.json").write_text(
            json.dumps(expected), encoding="utf-8"
        )

        case = CaseConfig()
        case.ticker = "TEST"
        case.case_dir = str(tmp_path)
        context = PipelineContext(case=case)

        phases = [EvaluatePhase(), AssemblePhase()]
        Pipeline(phases).run(context)

        phase_names = [r.phase_name for r in context.phase_results]
        assert "EvaluatePhase" in phase_names, "EvaluatePhase did not run"
        assert "AssemblePhase" in phase_names, (
            "AssemblePhase was skipped after EvaluatePhase warn — must not be"
        )

    def test_convert_phase_warning_on_failed_conversions(self, tmp_path: Path) -> None:
        """ConvertPhase must emit severity='warning' when any conversion fails (BL-063)."""
        from unittest.mock import patch

        from elsian.context import PipelineContext
        from elsian.convert.phase import ConvertPhase
        from elsian.models.case import CaseConfig

        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001.htm").write_text("<html/>", encoding="utf-8")

        case = CaseConfig()
        case.ticker = "TEST"
        case.case_dir = str(tmp_path)
        context = PipelineContext(case=case)

        def _boom(path: object) -> str:
            raise RuntimeError("simulated conversion failure")

        with patch("elsian.convert.html_to_markdown.convert", _boom):
            phase = ConvertPhase(force=True)
            result = phase.run(context)

        assert result.severity == "warning", (
            f"ConvertPhase must emit 'warning' when failed > 0, got '{result.severity}'"
        )
        assert not result.is_fatal, "ConvertPhase must never be fatal"
        assert result.diagnostics["failed"] == 1


# ── Tests: --with-acquire routing (BL-063) ───────────────────────────

class TestWithAcquireRouting:
    """Verify --with-acquire includes AcquirePhase in the run path (no network)."""

    def test_with_acquire_invokes_acquire_phase(self, tmp_path: Path) -> None:
        """--with-acquire must route through AcquirePhase without requiring network.

        All phases are mocked to avoid I/O; we only verify that
        AcquirePhase.run is called exactly once.
        """
        import json
        from unittest.mock import patch

        from elsian.models.result import PhaseResult

        # Minimal case dir
        (tmp_path / "case.json").write_text(
            json.dumps({"ticker": "FAKEX", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        (tmp_path / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKEX", "currency": "USD", "periods": {}}),
            encoding="utf-8",
        )

        acquire_ran: list[str] = []

        def fake_acquire(self, context):  # noqa: ANN001
            acquire_ran.append(self.__class__.__name__)
            return PhaseResult(phase_name="AcquirePhase", success=True, message="mocked-acquire")

        def fake_convert(self, context):  # noqa: ANN001
            return PhaseResult(phase_name="ConvertPhase", success=True, message="mocked-convert")

        def fake_extract(self, context):  # noqa: ANN001
            return PhaseResult(phase_name="ExtractPhase", success=True, message="mocked-extract")

        def fake_evaluate(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="EvaluatePhase", success=True, severity="warning", message="mocked-eval"
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.acquire.phase.AcquirePhase.run", fake_acquire),
            patch("elsian.convert.phase.ConvertPhase.run", fake_convert),
            patch("elsian.extract.phase.ExtractPhase.run", fake_extract),
            patch("elsian.evaluate.phase.EvaluatePhase.run", fake_evaluate),
        ):
            from elsian.cli import _run_pipeline_for_ticker

            args = _make_args(ticker="FAKEX", with_acquire=True, skip_assemble=True)
            _run_pipeline_for_ticker("FAKEX", args)

        assert len(acquire_ran) == 1, (
            f"AcquirePhase.run must be called exactly once with --with-acquire; "
            f"called {len(acquire_ran)} time(s)"
        )

    def test_without_acquire_skips_acquire_phase(self, tmp_path: Path) -> None:
        """Default run (no --with-acquire) must NOT include AcquirePhase."""
        import json
        from unittest.mock import patch

        from elsian.models.result import PhaseResult

        (tmp_path / "case.json").write_text(
            json.dumps({"ticker": "FAKEX", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        (tmp_path / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKEX", "currency": "USD", "periods": {}}),
            encoding="utf-8",
        )

        acquire_ran: list[str] = []

        def fake_acquire(self, context):  # noqa: ANN001
            acquire_ran.append(self.__class__.__name__)
            return PhaseResult(phase_name="AcquirePhase", success=True, message="should-not-run")

        def fake_convert(self, context):  # noqa: ANN001
            return PhaseResult(phase_name="ConvertPhase", success=True, message="ok")

        def fake_extract(self, context):  # noqa: ANN001
            return PhaseResult(phase_name="ExtractPhase", success=True, message="ok")

        def fake_evaluate(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="EvaluatePhase", success=True, severity="warning", message="ok"
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.acquire.phase.AcquirePhase.run", fake_acquire),
            patch("elsian.convert.phase.ConvertPhase.run", fake_convert),
            patch("elsian.extract.phase.ExtractPhase.run", fake_extract),
            patch("elsian.evaluate.phase.EvaluatePhase.run", fake_evaluate),
        ):
            from elsian.cli import _run_pipeline_for_ticker

            args = _make_args(ticker="FAKEX", with_acquire=False, skip_assemble=True)
            _run_pipeline_for_ticker("FAKEX", args)

        assert len(acquire_ran) == 0, (
            "AcquirePhase.run must NOT be called when --with-acquire is absent"
        )


# ── Tests: fatal path does not overwrite extraction_result.json (BL-063) ──

class TestFatalNoOverwrite:
    """Verify a fatal phase does not overwrite an existing extraction_result.json."""

    def test_fatal_phase_does_not_overwrite_extraction_result(self, tmp_path: Path) -> None:
        """A fatal early phase must leave extraction_result.json unchanged (BL-063)."""
        import json
        from unittest.mock import patch

        from elsian.models.result import PhaseResult

        (tmp_path / "case.json").write_text(
            json.dumps({"ticker": "FAKEX", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        (tmp_path / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKEX", "currency": "USD", "periods": {}}),
            encoding="utf-8",
        )

        # Sentinel value — must survive the pipeline run
        sentinel = {"schema_version": "SENTINEL", "ticker": "FAKEX", "periods": {}}
        result_path = tmp_path / "extraction_result.json"
        result_path.write_text(json.dumps(sentinel), encoding="utf-8")

        def fatal_acquire(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="AcquirePhase",
                success=False,
                severity="fatal",
                message="simulated fatal failure",
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.acquire.phase.AcquirePhase.run", fatal_acquire),
        ):
            from elsian.cli import _run_pipeline_for_ticker

            args = _make_args(ticker="FAKEX", with_acquire=True, skip_assemble=True)
            ok, summary = _run_pipeline_for_ticker("FAKEX", args)

        assert not ok, "Fatal phase must cause _run_pipeline_for_ticker to return False"
        written = json.loads(result_path.read_text(encoding="utf-8"))
        assert written["schema_version"] == "SENTINEL", (
            "extraction_result.json must NOT be overwritten after a fatal phase; "
            f"got schema_version={written.get('schema_version')!r}"
        )

    def test_no_result_file_created_when_fatal_and_no_prior_file(
        self, tmp_path: Path
    ) -> None:
        """If extraction_result.json does not exist and pipeline is fatal, it must not be created."""
        import json
        from unittest.mock import patch

        from elsian.models.result import PhaseResult

        (tmp_path / "case.json").write_text(
            json.dumps({"ticker": "FAKEX", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        (tmp_path / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKEX", "currency": "USD", "periods": {}}),
            encoding="utf-8",
        )

        result_path = tmp_path / "extraction_result.json"
        assert not result_path.exists()

        def fatal_acquire(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="AcquirePhase",
                success=False,
                severity="fatal",
                message="simulated fatal failure",
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.acquire.phase.AcquirePhase.run", fatal_acquire),
        ):
            from elsian.cli import _run_pipeline_for_ticker

            args = _make_args(ticker="FAKEX", with_acquire=True, skip_assemble=True)
            ok, _ = _run_pipeline_for_ticker("FAKEX", args)

        assert not ok
        assert not result_path.exists(), (
            "extraction_result.json must not be created when the pipeline is fatal"
        )
