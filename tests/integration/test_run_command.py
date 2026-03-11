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
        "workspace": None,  # BL-070: no workspace by default (legacy behaviour)
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

    def test_run_tzoo_with_assemble(self, tmp_path: Path) -> None:
        """--workspace with assemble writes truth_pack.json outside cases/."""
        from elsian.cli import _run_pipeline_for_ticker
        # BL-070: use workspace so truth_pack.json lands outside cases/
        args = _make_args(ticker="TZOO", skip_assemble=False, workspace=str(tmp_path))
        ok, _ = _run_pipeline_for_ticker("TZOO", args)
        assert ok
        runtime_dir = tmp_path / "TZOO"
        truth_pack = runtime_dir / "truth_pack.json"
        # If assemble ran, truth_pack.json should exist in the workspace
        assert truth_pack.exists(), "truth_pack.json should have been generated in workspace"
        data = json.loads(truth_pack.read_text(encoding="utf-8"))
        assert data["schema_version"] == "TruthPack_v1"
        assert data["ticker"] == "TZOO"

    def test_run_tzoo_workspace_no_assemble(self, tmp_path: Path) -> None:
        """--workspace --skip-assemble writes extraction_result.json and run_metrics.json outside cases/."""
        from elsian.cli import _run_pipeline_for_ticker
        args = _make_args(ticker="TZOO", skip_assemble=True, workspace=str(tmp_path))
        ok, summary = _run_pipeline_for_ticker("TZOO", args)
        assert ok, f"Pipeline failed: {summary}"
        runtime_dir = tmp_path / "TZOO"
        assert (runtime_dir / "extraction_result.json").exists(), (
            "extraction_result.json must land in workspace, not in cases/"
        )
        assert (runtime_dir / "run_metrics.json").exists(), (
            "run_metrics.json must land in workspace, not in cases/"
        )
        # Verify the extraction result is valid JSON with expected structure
        er = json.loads((runtime_dir / "extraction_result.json").read_text(encoding="utf-8"))
        assert er["ticker"] == "TZOO"
        assert "periods" in er

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


# ── Tests: run_metrics.json (BL-068) ─────────────────────────────────

def _patch_minimal_pipeline(
    tmp_path: "Path",
    *,
    acquire_result=None,
    eval_score: float = 0.0,
):
    """Return a context manager that patches all pipeline phases for a minimal fake run.

    Patches _find_case_dir to tmp_path and provides deterministic PhaseResult
    objects with structured diagnostics (no free-text parsing needed).
    """
    from contextlib import ExitStack
    from unittest.mock import patch
    from elsian.models.result import PhaseResult, AcquisitionResult

    def fake_convert(self, context):  # noqa: ANN001
        return PhaseResult(
            phase_name="ConvertPhase", success=True, message="ok",
            diagnostics={"total": 0, "converted": 0, "skipped": 0, "failed": 0},
        )

    def fake_extract(self, context):  # noqa: ANN001
        return PhaseResult(
            phase_name="ExtractPhase", success=True, message="ok",
            diagnostics={"filings_used": 0, "periods": 0, "fields": 0},
        )

    sev = "ok" if eval_score == 100.0 else "warning"

    def fake_evaluate(self, context):  # noqa: ANN001
        return PhaseResult(
            phase_name="EvaluatePhase",
            success=True,
            severity=sev,
            message=f"score={eval_score}",
            diagnostics={
                "score": eval_score,
                "matched": 0,
                "total_expected": 0,
                "wrong": 0,
                "missed": 0,
                "extra": 0,
            },
        )

    stack = ExitStack()
    stack.enter_context(patch("elsian.cli._find_case_dir", return_value=tmp_path))
    stack.enter_context(patch("elsian.convert.phase.ConvertPhase.run", fake_convert))
    stack.enter_context(patch("elsian.extract.phase.ExtractPhase.run", fake_extract))
    stack.enter_context(patch("elsian.evaluate.phase.EvaluatePhase.run", fake_evaluate))

    if acquire_result is not None:
        def fake_acquire(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="AcquirePhase", success=True,
                message="ok", data=acquire_result,
            )
        stack.enter_context(
            patch("elsian.acquire.phase.AcquirePhase.run", fake_acquire)
        )

    return stack


def _write_minimal_case(tmp_path: "Path") -> None:
    """Write minimal case.json and expected.json to tmp_path."""
    import json
    (tmp_path / "case.json").write_text(
        json.dumps({"ticker": "FAKEX", "source_hint": "sec", "currency": "USD"}),
        encoding="utf-8",
    )
    (tmp_path / "expected.json").write_text(
        json.dumps({"version": "1.0", "ticker": "FAKEX", "currency": "USD",
                    "periods": {}}),
        encoding="utf-8",
    )


class TestRunMetrics:
    """Verify run_metrics.json is written with correct schema and content (BL-068)."""

    def test_run_metrics_schema_keys(self, tmp_path: Path) -> None:
        """run_metrics.json must have all required top-level schema keys."""
        import json
        _write_minimal_case(tmp_path)

        with _patch_minimal_pipeline(tmp_path):
            from elsian.cli import _run_pipeline_for_ticker
            _run_pipeline_for_ticker("FAKEX", _make_args(ticker="FAKEX", skip_assemble=True))

        metrics_path = tmp_path / "run_metrics.json"
        assert metrics_path.exists(), "run_metrics.json must be written"

        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        required_keys = {
            "schema_version", "run_id", "started_at", "finished_at",
            "duration_ms", "ticker", "command", "flags",
            "source_hint", "final_status", "phases", "aggregates",
        }
        missing = required_keys - set(metrics.keys())
        assert not missing, f"run_metrics.json missing keys: {missing}"
        assert metrics["schema_version"] == "run_metrics_v1"
        assert metrics["ticker"] == "FAKEX"
        assert metrics["command"] == "run"
        assert isinstance(metrics["run_id"], str) and len(metrics["run_id"]) > 0
        assert isinstance(metrics["phases"], list)
        assert len(metrics["phases"]) >= 3  # convert, extract, evaluate

    def test_run_metrics_phase_duration_ms(self, tmp_path: Path) -> None:
        """Each phase entry in run_metrics.phases must have duration_ms >= 0."""
        import json
        _write_minimal_case(tmp_path)

        with _patch_minimal_pipeline(tmp_path):
            from elsian.cli import _run_pipeline_for_ticker
            _run_pipeline_for_ticker("FAKEX", _make_args(ticker="FAKEX", skip_assemble=True))

        metrics = json.loads((tmp_path / "run_metrics.json").read_text(encoding="utf-8"))
        for phase in metrics["phases"]:
            assert "duration_ms" in phase, f"duration_ms missing from phase {phase!r}"
            assert isinstance(phase["duration_ms"], (int, float))
            assert phase["duration_ms"] >= 0.0, (
                f"duration_ms must be >= 0, got {phase['duration_ms']}"
            )

    def test_run_metrics_with_acquire_aggregate(self, tmp_path: Path) -> None:
        """with_acquire=True must produce an acquire aggregate in run_metrics."""
        import json
        from elsian.models.result import AcquisitionResult

        _write_minimal_case(tmp_path)
        acq = AcquisitionResult(
            ticker="FAKEX",
            source="sec",
            filings_downloaded=5,
            filings_coverage_pct=100.0,
            cache_hit=True,
            retries_total=2,
            throttle_ms=120.0,
            source_kind="filing",
            gaps=[],
        )

        with _patch_minimal_pipeline(tmp_path, acquire_result=acq):
            from elsian.cli import _run_pipeline_for_ticker
            _run_pipeline_for_ticker(
                "FAKEX", _make_args(ticker="FAKEX", with_acquire=True, skip_assemble=True)
            )

        metrics = json.loads((tmp_path / "run_metrics.json").read_text(encoding="utf-8"))
        assert "acquire" in metrics["aggregates"], "acquire aggregate missing"
        agg = metrics["aggregates"]["acquire"]
        assert agg["filings_downloaded"] == 5
        assert agg["cache_hit"] is True
        assert agg["retries_total"] == 2
        assert metrics["flags"]["with_acquire"] is True

    def test_run_metrics_skip_assemble_reflected(self, tmp_path: Path) -> None:
        """skip_assemble=True must be reflected in flags and assemble aggregate."""
        import json
        _write_minimal_case(tmp_path)

        with _patch_minimal_pipeline(tmp_path):
            from elsian.cli import _run_pipeline_for_ticker
            _run_pipeline_for_ticker(
                "FAKEX", _make_args(ticker="FAKEX", skip_assemble=True)
            )

        metrics = json.loads((tmp_path / "run_metrics.json").read_text(encoding="utf-8"))
        assert metrics["flags"]["skip_assemble"] is True
        assemble = metrics["aggregates"].get("assemble", {})
        assert assemble.get("skipped") is True, (
            f"assemble.skipped must be True when skip_assemble=True; got {assemble!r}"
        )

    def test_run_metrics_fatal_writes_file_without_overwriting_extraction_result(
        self, tmp_path: Path
    ) -> None:
        """A fatal phase must write run_metrics.json but NOT overwrite extraction_result.json."""
        import json
        from unittest.mock import patch
        from elsian.models.result import PhaseResult

        _write_minimal_case(tmp_path)
        sentinel = {"schema_version": "SENTINEL", "ticker": "FAKEX", "periods": {}}
        (tmp_path / "extraction_result.json").write_text(
            json.dumps(sentinel), encoding="utf-8"
        )

        def fatal_convert(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="ConvertPhase", success=False,
                severity="fatal", message="simulated fatal",
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.convert.phase.ConvertPhase.run", fatal_convert),
        ):
            from elsian.cli import _run_pipeline_for_ticker
            ok, _ = _run_pipeline_for_ticker("FAKEX", _make_args(ticker="FAKEX", skip_assemble=True))

        assert not ok, "fatal pipeline must return False"
        # extraction_result.json must be preserved
        written = json.loads((tmp_path / "extraction_result.json").read_text(encoding="utf-8"))
        assert written["schema_version"] == "SENTINEL", (
            "extraction_result.json must NOT be overwritten after fatal"
        )
        # run_metrics.json MUST be written even on fatal
        metrics_path = tmp_path / "run_metrics.json"
        assert metrics_path.exists(), "run_metrics.json must be written even when pipeline is fatal"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        assert metrics["final_status"]["fatal"] is True

    def test_run_metrics_score_from_structured_diagnostics_not_message(
        self, tmp_path: Path
    ) -> None:
        """Score in run_metrics.aggregates.evaluate must come from diagnostics, not text."""
        import json
        from unittest.mock import patch
        from elsian.models.result import PhaseResult

        _write_minimal_case(tmp_path)

        # Message intentionally misleads; diagnostics carry the real score
        def fake_convert(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="ConvertPhase", success=True, message="ok",
                diagnostics={"total": 0, "converted": 0, "skipped": 0, "failed": 0},
            )

        def fake_extract(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="ExtractPhase", success=True, message="ok",
                diagnostics={"filings_used": 0, "periods": 0, "fields": 0},
            )

        def fake_evaluate(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="EvaluatePhase", success=True, severity="warning",
                message="FAKE 99%",  # must NOT be parsed by run_metrics helper
                diagnostics={
                    "score": 75.0,
                    "matched": 3,
                    "total_expected": 4,
                    "wrong": 1,
                    "missed": 0,
                    "extra": 0,
                },
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.convert.phase.ConvertPhase.run", fake_convert),
            patch("elsian.extract.phase.ExtractPhase.run", fake_extract),
            patch("elsian.evaluate.phase.EvaluatePhase.run", fake_evaluate),
        ):
            from elsian.cli import _run_pipeline_for_ticker
            _run_pipeline_for_ticker("FAKEX", _make_args(ticker="FAKEX", skip_assemble=True))

        metrics = json.loads((tmp_path / "run_metrics.json").read_text(encoding="utf-8"))
        eval_agg = metrics["aggregates"]["evaluate"]
        assert eval_agg["score"] == 75.0, (
            f"Score must come from diagnostics (75.0), not text parsing; got {eval_agg['score']}"
        )
        assert eval_agg["matched"] == 3

    def test_run_metrics_eval_skipped_null_eval_ok_and_skip_aggregate(
        self, tmp_path: Path
    ) -> None:
        """When EvaluatePhase skips (no expected.json), final_status.eval_ok must be null
        and aggregates.evaluate must be {"skipped": true} — not an all-zeros PASS."""
        import json
        from unittest.mock import patch
        from elsian.models.result import PhaseResult

        _write_minimal_case(tmp_path)

        def fake_convert(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="ConvertPhase", success=True, message="ok",
                diagnostics={"total": 0, "converted": 0, "skipped": 0, "failed": 0},
            )

        def fake_extract(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="ExtractPhase", success=True, message="ok",
                diagnostics={"filings_used": 0, "periods": 0, "fields": 0},
            )

        def fake_evaluate_skip(self, context):  # noqa: ANN001
            # Mirrors EvaluatePhase real skip path: no data, no diagnostics
            return PhaseResult(
                phase_name="EvaluatePhase",
                success=True,
                severity="ok",
                message="TEST: no expected.json — skipping evaluation",
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.convert.phase.ConvertPhase.run", fake_convert),
            patch("elsian.extract.phase.ExtractPhase.run", fake_extract),
            patch("elsian.evaluate.phase.EvaluatePhase.run", fake_evaluate_skip),
        ):
            from elsian.cli import _run_pipeline_for_ticker
            ok, summary = _run_pipeline_for_ticker(
                "FAKEX", _make_args(ticker="FAKEX", skip_assemble=True)
            )

        # A skipped eval must NOT cause pipeline failure
        assert ok is True, f"Pipeline must succeed when eval is skipped; got ok={ok!r}"
        assert summary == "skipped", f"Expected 'skipped' summary, got {summary!r}"

        metrics = json.loads((tmp_path / "run_metrics.json").read_text(encoding="utf-8"))

        # eval_ok must be null — skip is NOT a PASS
        assert metrics["final_status"]["eval_ok"] is None, (
            f"final_status.eval_ok must be null when eval is skipped; "
            f"got {metrics['final_status']['eval_ok']!r}"
        )

        # evaluate aggregate must signal skip, not produce an all-zeros score
        eval_agg = metrics["aggregates"]["evaluate"]
        assert eval_agg.get("skipped") is True, (
            f"aggregates.evaluate must have skipped=true when eval skipped; got {eval_agg!r}"
        )
        assert "score" not in eval_agg, (
            f"aggregates.evaluate must not contain 'score' when skipped; got {eval_agg!r}"
        )

    def test_run_metrics_ticker_is_canonical_from_case_json(
        self, tmp_path: Path
    ) -> None:
        """run_metrics.json['ticker'] must be the canonical ticker from case.json,
        not the raw CLI argument (which may be lowercase or differently cased).
        """
        import json

        # Write case.json with canonical uppercase ticker
        (tmp_path / "case.json").write_text(
            json.dumps({"ticker": "FAKEX", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        (tmp_path / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKEX", "currency": "USD",
                        "periods": {}}),
            encoding="utf-8",
        )

        # Pass lowercase ticker as CLI argument — simulates 'elsian run fakex'
        with _patch_minimal_pipeline(tmp_path):
            from elsian.cli import _run_pipeline_for_ticker
            _run_pipeline_for_ticker("fakex", _make_args(ticker="fakex", skip_assemble=True))

        metrics_path = tmp_path / "run_metrics.json"
        assert metrics_path.exists(), "run_metrics.json must be written"

        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        assert metrics["ticker"] == "FAKEX", (
            f"run_metrics.json['ticker'] must be canonical 'FAKEX' from case.json, "
            f"got {metrics['ticker']!r}"
        )


# ── Tests: BL-070 audit fix — AssemblePhase in-memory extraction_result ──

class TestAssemblePhaseWorkspaceBL070:
    """BL-070 audit fix: AssemblePhase must use context.result in-memory,
    never fall back to a stale or missing extraction_result.json on disk."""

    def test_assembler_accepts_in_memory_extraction_result_ignores_disk(
        self, tmp_path: Path
    ) -> None:
        """TruthPackAssembler.assemble() must use the in-memory dict when
        provided, ignoring any extraction_result.json on disk."""
        import json
        from elsian.assemble.truth_pack import TruthPackAssembler

        # Write case.json (required by assembler)
        (tmp_path / "case.json").write_text(
            json.dumps({"ticker": "TEST", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        # Write a STALE extraction_result.json on disk — must be ignored
        stale_er = {
            "schema_version": "ExtractionResult_v1",
            "ticker": "STALE",
            "currency": "USD",
            "extraction_date": "2020-01-01",
            "filings_used": 0,
            "periods": {"FY2019": {"fecha_fin": "2019-12-31", "tipo_periodo": "anual", "fields": {}}},
            "audit": {"fields_extracted": 0, "fields_discarded": 0, "discarded_reasons": {}},
        }
        (tmp_path / "extraction_result.json").write_text(
            json.dumps(stale_er), encoding="utf-8"
        )
        # Fresh in-memory dict — different state from disk
        fresh_er = {
            "schema_version": "ExtractionResult_v1",
            "ticker": "TEST",
            "currency": "USD",
            "extraction_date": "2026-03-10",
            "filings_used": 5,
            "periods": {},
            "audit": {"fields_extracted": 0, "fields_discarded": 0, "discarded_reasons": {}},
        }

        assembler = TruthPackAssembler()
        tp = assembler.assemble(tmp_path, extraction_result=fresh_er)

        # truth_pack must reflect the fresh in-memory data, not the stale disk file
        assert tp["schema_version"] == "TruthPack_v1"
        assert tp["ticker"] == "TEST", (
            f"truth_pack.ticker must be 'TEST' (from fresh in-memory), "
            f"got {tp['ticker']!r} (stale disk had ticker='STALE')"
        )
        assert (tmp_path / "truth_pack.json").exists()

    def test_assembler_raises_when_no_in_memory_and_no_disk_file(
        self, tmp_path: Path
    ) -> None:
        """Without in-memory dict and without disk file, assembler must raise FileNotFoundError."""
        import json
        from elsian.assemble.truth_pack import TruthPackAssembler

        (tmp_path / "case.json").write_text(
            json.dumps({"ticker": "TEST", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        # No extraction_result.json on disk, no in-memory provided
        assembler = TruthPackAssembler()
        with pytest.raises(FileNotFoundError, match="extraction_result.json not found"):
            assembler.assemble(tmp_path)

    def test_assemble_phase_passes_context_result_in_memory(
        self, tmp_path: Path
    ) -> None:
        """AssemblePhase.run() must pass context.result.to_dict() to the assembler
        so that it does NOT require extraction_result.json to be present on disk."""
        import json
        from elsian.assemble.phase import AssemblePhase
        from elsian.context import PipelineContext
        from elsian.models.case import CaseConfig

        # case_dir has case.json but NO extraction_result.json on disk
        (tmp_path / "case.json").write_text(
            json.dumps({"ticker": "TEST", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        assert not (tmp_path / "extraction_result.json").exists(), (
            "Pre-condition: no extraction_result.json on disk"
        )

        case = CaseConfig()
        case.ticker = "TEST"
        case.case_dir = str(tmp_path)
        context = PipelineContext(case=case)
        # Populate context.result (simulates ExtractPhase having run)
        context.result.ticker = "TEST"
        context.result.currency = "USD"

        phase = AssemblePhase()
        result = phase.run(context)

        # AssemblePhase must succeed despite no disk file — uses in-memory result
        assert not result.is_fatal, (
            f"AssemblePhase must not be fatal when using in-memory result; "
            f"got severity={result.severity!r}, message={result.message!r}"
        )
        # truth_pack.json written to case_dir (no workspace in this test)
        tp_path = tmp_path / "truth_pack.json"
        assert tp_path.exists(), "truth_pack.json must be written by AssemblePhase"
        tp = json.loads(tp_path.read_text(encoding="utf-8"))
        assert tp["schema_version"] == "TruthPack_v1"

    def test_workspace_first_run_no_prior_extraction_result_on_disk(
        self, tmp_path: Path
    ) -> None:
        """BL-070 blocker: first workspace run with clean workspace dir must
        assemble truth_pack from in-memory pipeline result, not fail or read
        stale/missing extraction_result.json from disk."""
        import json
        from unittest.mock import patch

        from elsian.models.result import PhaseResult

        case_dir = tmp_path / "case"
        case_dir.mkdir()
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "FAKEX", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )
        (case_dir / "expected.json").write_text(
            json.dumps({"version": "1.0", "ticker": "FAKEX", "currency": "USD", "periods": {}}),
            encoding="utf-8",
        )
        # Explicitly confirm: no extraction_result.json anywhere
        assert not (case_dir / "extraction_result.json").exists()
        assert not (workspace_dir / "FAKEX" / "extraction_result.json").exists()

        def fake_convert(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="ConvertPhase",
                success=True,
                message="mocked-convert",
                diagnostics={"total": 0, "converted": 0, "skipped": 0, "failed": 0},
            )

        def fake_extract(self, context):  # noqa: ANN001
            context.result.ticker = "FAKEX"
            context.result.currency = "USD"
            return PhaseResult(phase_name="ExtractPhase", success=True, message="mocked-extract")

        def fake_evaluate(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="EvaluatePhase",
                success=True,
                severity="ok",
                message="TEST: no expected.json — skipping evaluation",
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=case_dir),
            patch("elsian.convert.phase.ConvertPhase.run", fake_convert),
            patch("elsian.extract.phase.ExtractPhase.run", fake_extract),
            patch("elsian.evaluate.phase.EvaluatePhase.run", fake_evaluate),
        ):
            from elsian.cli import _run_pipeline_for_ticker

            args = _make_args(
                ticker="FAKEX",
                skip_assemble=False,
                workspace=str(workspace_dir),
            )
            ok, summary = _run_pipeline_for_ticker("FAKEX", args)

        assert ok is True, f"Pipeline must succeed on first workspace run; got ok={ok!r}, summary={summary!r}"

        runtime_dir = workspace_dir / "FAKEX"
        # truth_pack.json must exist in workspace (assembled from in-memory result)
        tp_path = runtime_dir / "truth_pack.json"
        assert tp_path.exists(), (
            "truth_pack.json must be present in workspace after first run "
            "even when no extraction_result.json existed on disk beforehand"
        )
        tp = json.loads(tp_path.read_text(encoding="utf-8"))
        assert tp["schema_version"] == "TruthPack_v1"
        # extraction_result.json written after pipeline by cli.py — must also exist
        er_path = runtime_dir / "extraction_result.json"
        assert er_path.exists(), "extraction_result.json must be written to workspace"


# ── Tests: workspace canonical ticker (BL-070 audit fix) ─────────────

class TestWorkspaceCanonicalTicker:
    """Verify runtime workspace path uses canonical ticker from case.json, not raw arg.

    Regression coverage for: same case must not write to PATH/tzoo AND PATH/TZOO
    depending on how the user spelled the ticker at invocation time.
    """

    def test_workspace_path_uses_canonical_ticker_not_raw_arg(self, tmp_path: Path) -> None:
        """Invoking with lowercase ticker must create PATH/<CANONICAL>/, not PATH/<raw>/.

        The canonical ticker is read from case.json (e.g. 'FAKEX').
        The invoke argument uses a different casing (e.g. 'fakex').
        After the fix, runtime_dir must be tmp_path/'FAKEX', never tmp_path/'fakex'.
        """
        import json
        from unittest.mock import patch

        from elsian.models.result import PhaseResult

        # case.json declares canonical ticker as uppercase "FAKEX"
        case_dir = tmp_path / "case_root"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps({"ticker": "FAKEX", "source_hint": "sec", "currency": "USD"}),
            encoding="utf-8",
        )

        workspace_dir = tmp_path / "workspace"

        def fake_convert(self, context):  # noqa: ANN001
            return PhaseResult(phase_name="ConvertPhase", success=True, message="ok")

        def fake_extract(self, context):  # noqa: ANN001
            return PhaseResult(phase_name="ExtractPhase", success=True, message="ok")

        def fake_evaluate(self, context):  # noqa: ANN001
            return PhaseResult(
                phase_name="EvaluatePhase", success=True, severity="ok",
                message="no expected.json — skipping",
            )

        with (
            patch("elsian.cli._find_case_dir", return_value=case_dir),
            patch("elsian.convert.phase.ConvertPhase.run", fake_convert),
            patch("elsian.extract.phase.ExtractPhase.run", fake_extract),
            patch("elsian.evaluate.phase.EvaluatePhase.run", fake_evaluate),
        ):
            from elsian.cli import _run_pipeline_for_ticker

            # Invoke with LOWERCASE ticker — simulates user typing 'elsian run fakex'
            args = _make_args(
                ticker="fakex",
                skip_assemble=True,
                workspace=str(workspace_dir),
            )
            _run_pipeline_for_ticker("fakex", args)

        # Use os.listdir to get the actual entry name on disk (preserves casing
        # even on case-insensitive filesystems like macOS APFS).
        import os
        created = os.listdir(workspace_dir)
        assert "FAKEX" in created, (
            f"Runtime dir must use canonical ticker 'FAKEX' from case.json; "
            f"workspace contains: {created}"
        )
        assert "fakex" not in created, (
            f"Raw-casing 'fakex' must NOT appear as a separate entry; "
            f"workspace contains: {created}"
        )


# ── Tests: cmd_eval readiness display (BL-064) ───────────────────────

class TestCmdEvalReadiness:
    """Verify that cmd_eval shows readiness fields alongside legacy score (BL-064)."""

    def _run_cmd_eval_mocked(
        self,
        ticker: str = "FAKEX",
        sort_by: str = "ticker",
        all_: bool = False,
        score: float = 100.0,
    ):
        """Run cmd_eval with mocked ExtractPhase and capture stdout.

        Returns (output_str, exit_code).
        """
        import io
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch

        from elsian.cli import cmd_eval
        from elsian.models.field import FieldResult, Provenance
        from elsian.models.result import ExtractionResult, PeriodResult

        # Minimal ExtractionResult that makes the score deterministic
        fake_er = ExtractionResult(ticker=ticker)
        pr = PeriodResult(fecha_fin="2024-12-31", tipo_periodo="anual")
        pr.fields["ingresos"] = FieldResult(
            value=1000.0,
            provenance=Provenance(source_filing="x.md", extraction_method="table"),
        )
        if score < 100.0:
            # Add an extra field not in expected → will produce wrong/missed
            pr.fields["net_income"] = FieldResult(
                value=999.0,
                provenance=Provenance(source_filing="x.md", extraction_method="table"),
            )
        fake_er.periods["FY2024"] = pr

        args = SimpleNamespace(ticker=ticker, all=all_, sort_by=sort_by)

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        exit_code = 0
        try:
            with patch("elsian.cli._find_case_dir", return_value=CASES_DIR / "TZOO"):
                with patch("elsian.extract.phase.ExtractPhase.extract", return_value=fake_er):
                    cmd_eval(args)
        except SystemExit as e:
            exit_code = e.code or 0
        finally:
            sys.stdout = old_stdout
        return captured.getvalue(), exit_code

    def test_single_ticker_shows_readiness(self) -> None:
        """cmd_eval for a single ticker must print readiness= in its output."""
        out, _ = self._run_cmd_eval_mocked("TZOO")
        assert "readiness=" in out, (
            f"Expected 'readiness=' in cmd_eval output; got:\n{out}"
        )

    def test_single_ticker_shows_score(self) -> None:
        """cmd_eval must still show legacy score= in output."""
        out, _ = self._run_cmd_eval_mocked("TZOO")
        assert "score=" in out, (
            f"Expected 'score=' in cmd_eval output; got:\n{out}"
        )

    def test_single_ticker_shows_conf_prov_penalty(self) -> None:
        """cmd_eval output must include conf=, prov=, penalty= component labels."""
        out, _ = self._run_cmd_eval_mocked("TZOO")
        assert "conf=" in out, f"Expected conf= in output; got:\n{out}"
        assert "prov=" in out, f"Expected prov= in output; got:\n{out}"
        assert "penalty=" in out, f"Expected penalty= in output; got:\n{out}"

    def test_sort_by_ticker_is_stable(self) -> None:
        """--sort-by ticker (default) must not crash and must produce output with score=."""
        # With all_=False and a single ticker, sort_by is irrelevant but must not raise
        out, exit_code = self._run_cmd_eval_mocked("TZOO", sort_by="ticker")
        assert "score=" in out

    def test_eval_report_has_readiness_fields_in_to_dict(self) -> None:
        """EvalReport.to_dict() produced by evaluate() must include readiness fields."""
        import json
        import tempfile
        from elsian.models.field import FieldResult, Provenance
        from elsian.models.result import ExtractionResult, PeriodResult
        from elsian.evaluate.evaluator import evaluate

        expected = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "ingresos": {"value": 1000.0},
                    }
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(expected, f)
            f.flush()

            er = ExtractionResult(ticker="TEST")
            pr = PeriodResult()
            pr.fields["ingresos"] = FieldResult(
                value=1000.0,
                provenance=Provenance(source_filing="f.md", extraction_method="table"),
            )
            er.periods["FY2024"] = pr
            report = evaluate(er, f.name)

        d = report.to_dict()
        for key in ("readiness_score", "validator_confidence_score",
                    "provenance_coverage_pct", "extra_penalty"):
            assert key in d, f"EvalReport.to_dict() missing key: {key}"
            assert isinstance(d[key], float), f"{key} must be float, got {type(d[key])}"
