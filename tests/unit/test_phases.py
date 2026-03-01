"""Tests for pipeline phase wiring: AcquirePhase, ExtractPhase, EvaluatePhase."""

from elsian.pipeline import PipelinePhase, Pipeline
from elsian.context import PipelineContext
from elsian.models.result import PhaseResult


# ── Verify inheritance ────────────────────────────────────────────────


def test_extract_phase_is_pipeline_phase():
    from elsian.extract.phase import ExtractPhase
    phase = ExtractPhase()
    assert isinstance(phase, PipelinePhase)


def test_acquire_phase_is_pipeline_phase():
    from elsian.acquire.phase import AcquirePhase
    phase = AcquirePhase()
    assert isinstance(phase, PipelinePhase)


def test_evaluate_phase_is_pipeline_phase():
    from elsian.evaluate.phase import EvaluatePhase
    phase = EvaluatePhase()
    assert isinstance(phase, PipelinePhase)


# ── run() method contract ─────────────────────────────────────────────


def test_extract_phase_run_returns_phase_result():
    """ExtractPhase.run() should fail gracefully with empty case_dir."""
    from elsian.extract.phase import ExtractPhase
    phase = ExtractPhase()
    ctx = PipelineContext()
    result = phase.run(ctx)
    assert isinstance(result, PhaseResult)
    assert result.phase_name == "ExtractPhase"
    assert not result.success  # no case_dir set


def test_evaluate_phase_run_no_expected():
    """EvaluatePhase.run() succeeds when no expected.json exists."""
    from elsian.evaluate.phase import EvaluatePhase
    from elsian.models.case import CaseConfig
    phase = EvaluatePhase()
    ctx = PipelineContext(case=CaseConfig(ticker="FAKE", case_dir="/nonexistent"))
    result = phase.run(ctx)
    assert isinstance(result, PhaseResult)
    assert result.success
    assert "skipping" in result.message.lower()


# ── Pipeline integration ──────────────────────────────────────────────


def test_pipeline_with_extract_and_evaluate():
    """Pipeline chains ExtractPhase + EvaluatePhase (both fail gracefully)."""
    from elsian.extract.phase import ExtractPhase
    from elsian.evaluate.phase import EvaluatePhase
    phases = [ExtractPhase(), EvaluatePhase()]
    pipeline = Pipeline(phases)
    ctx = PipelineContext()
    result = pipeline.run(ctx)
    # ExtractPhase fails (no case_dir), pipeline stops
    assert len(result.errors) == 1
    assert "ExtractPhase" in result.errors[0]
