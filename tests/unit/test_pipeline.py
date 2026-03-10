"""Tests for Pipeline orchestrator and PhaseResult severity model (BL-063)."""

import time

from elsian.pipeline import Pipeline, PipelinePhase
from elsian.context import PipelineContext
from elsian.models.result import PhaseResult


class FakePhase(PipelinePhase):
    def __init__(self, name: str, success: bool = True):
        self._name = name
        self._success = success

    def run(self, context: PipelineContext) -> PhaseResult:
        return PhaseResult(phase_name=self._name, success=self._success, message="ok")


class FailPhase(PipelinePhase):
    def run(self, context: PipelineContext) -> PhaseResult:
        return PhaseResult(phase_name="fail", success=False, message="boom")


class WarnPhase(PipelinePhase):
    def run(self, context: PipelineContext) -> PhaseResult:
        return PhaseResult(
            phase_name="warn", success=True, severity="warning", message="meh"
        )


class ExplicitFatalPhase(PipelinePhase):
    def run(self, context: PipelineContext) -> PhaseResult:
        return PhaseResult(phase_name="fatal", severity="fatal", message="hard stop")


# ── Existing behaviour (preserved) ────────────────────────────────────

def test_pipeline_runs_all_phases():
    p = Pipeline([FakePhase("a"), FakePhase("b"), FakePhase("c")])
    ctx = PipelineContext()
    result = p.run(ctx)
    assert len(result.errors) == 0


def test_pipeline_stops_on_failure():
    """success=False ⇒ severity promoted to fatal ⇒ pipeline stops."""
    p = Pipeline([FakePhase("a"), FailPhase(), FakePhase("c")])
    ctx = PipelineContext()
    result = p.run(ctx)
    assert len(result.errors) == 1
    assert "boom" in result.errors[0]


# ── New severity semantics (BL-063) ───────────────────────────────────

def test_pipeline_continues_on_warning():
    """A warning phase must NOT stop the pipeline."""
    ran: list[str] = []

    class TrackPhase(PipelinePhase):
        def run(self, ctx: PipelineContext) -> PhaseResult:
            ran.append("after")
            return PhaseResult(phase_name="after", success=True, message="ok")

    p = Pipeline([FakePhase("a"), WarnPhase(), TrackPhase()])
    ctx = PipelineContext()
    p.run(ctx)
    assert "after" in ran
    assert len(ctx.errors) == 0  # warnings do not populate errors


def test_pipeline_stops_on_explicit_fatal():
    """An explicit severity='fatal' must halt the pipeline."""
    ran: list[str] = []

    class AfterPhase(PipelinePhase):
        def run(self, ctx: PipelineContext) -> PhaseResult:
            ran.append("after")
            return PhaseResult(phase_name="after", success=True)

    p = Pipeline([ExplicitFatalPhase(), AfterPhase()])
    ctx = PipelineContext()
    p.run(ctx)
    assert "after" not in ran
    assert len(ctx.errors) == 1


def test_pipeline_accumulates_phase_results():
    """context.phase_results must contain one entry per phase run."""
    p = Pipeline([FakePhase("a"), FakePhase("b"), FakePhase("c")])
    ctx = PipelineContext()
    p.run(ctx)
    assert len(ctx.phase_results) == 3
    assert ctx.phase_results[0].phase_name == "a"
    assert ctx.phase_results[2].phase_name == "c"


def test_pipeline_accumulates_until_fatal():
    """phase_results must contain entries up to and including the fatal phase."""
    p = Pipeline([FakePhase("a"), ExplicitFatalPhase(), FakePhase("c")])
    ctx = PipelineContext()
    p.run(ctx)
    assert len(ctx.phase_results) == 2
    assert ctx.phase_results[1].phase_name == "fatal"


def test_on_phase_done_called_for_each_phase():
    """on_phase_done callback must fire once per phase run."""
    seen: list[str] = []

    def _cb(result: PhaseResult) -> None:
        seen.append(result.phase_name)

    p = Pipeline([FakePhase("x"), WarnPhase(), FakePhase("z")], on_phase_done=_cb)
    ctx = PipelineContext()
    p.run(ctx)
    assert seen == ["x", "warn", "z"]


def test_on_phase_done_called_for_fatal_before_stopping():
    """on_phase_done must be called for the fatal phase before the pipeline stops."""
    seen: list[str] = []

    def _cb(result: PhaseResult) -> None:
        seen.append(result.phase_name)

    p = Pipeline([FakePhase("a"), ExplicitFatalPhase(), FakePhase("c")], on_phase_done=_cb)
    ctx = PipelineContext()
    p.run(ctx)
    assert seen == ["a", "fatal"]


# ── PhaseResult backward compatibility ───────────────────────────────

def test_phase_result_backward_compat_success_false_becomes_fatal():
    """success=False with no explicit severity must silently promote to fatal."""
    r = PhaseResult(success=False, message="old api")
    assert r.severity == "fatal"
    assert r.is_fatal


def test_phase_result_success_true_is_ok_by_default():
    r = PhaseResult(success=True, message="fine")
    assert r.severity == "ok"
    assert not r.is_fatal


def test_phase_result_warning_not_fatal():
    r = PhaseResult(success=True, severity="warning", message="degraded")
    assert not r.is_fatal


def test_phase_result_explicit_fatal_is_fatal():
    r = PhaseResult(severity="fatal", message="gone")
    assert r.is_fatal


# ── BL-068: duration_ms on PhaseResult ───────────────────────────────

def test_phase_result_has_duration_ms_field():
    """PhaseResult must have a duration_ms field defaulting to 0.0."""
    r = PhaseResult(phase_name="test", success=True)
    assert hasattr(r, "duration_ms")
    assert r.duration_ms == 0.0


def test_pipeline_sets_duration_ms_on_phase_result():
    """Pipeline must set duration_ms >= 0 on each PhaseResult after phase.run()."""
    class TrivialPhase(PipelinePhase):
        def run(self, ctx: PipelineContext) -> PhaseResult:
            return PhaseResult(phase_name="trivial", success=True)

    p = Pipeline([TrivialPhase()])
    ctx = PipelineContext()
    p.run(ctx)
    assert ctx.phase_results[0].duration_ms >= 0.0


def test_pipeline_sets_duration_ms_for_all_phases():
    """All phases that run must have duration_ms set (>= 0) by the Pipeline."""
    p = Pipeline([FakePhase("a"), FakePhase("b"), WarnPhase()])
    ctx = PipelineContext()
    p.run(ctx)
    assert len(ctx.phase_results) == 3
    for r in ctx.phase_results:
        assert r.duration_ms >= 0.0, (
            f"Phase {r.phase_name!r} has negative duration_ms={r.duration_ms}"
        )


def test_pipeline_duration_ms_stops_at_fatal_phase():
    """Only phases that ran (up to and including fatal) get duration_ms."""
    p = Pipeline([FakePhase("a"), ExplicitFatalPhase(), FakePhase("c")])
    ctx = PipelineContext()
    p.run(ctx)
    # Only 2 phases ran; the third was not executed
    assert len(ctx.phase_results) == 2
    for r in ctx.phase_results:
        assert r.duration_ms >= 0.0


# ── BL-068: run_metrics eval skip semantics ───────────────────────────

def test_build_run_metrics_eval_skip_produces_null_eval_ok_and_skip_aggregate():
    """build_run_metrics must emit eval_ok=None and evaluate.skipped=True when
    EvaluatePhase returns the skip-style PhaseResult (no data, no diagnostics)."""
    from unittest.mock import MagicMock
    from elsian.run_metrics import build_run_metrics

    skip_result = PhaseResult(
        phase_name="EvaluatePhase",
        success=True,
        severity="ok",
        message="no expected.json — skipping evaluation",
        # data=None (default), diagnostics=None (default)
    )
    ctx = MagicMock()
    ctx.phase_results = [skip_result]

    metrics = build_run_metrics(
        run_id="test-skip-id",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        ticker="TEST",
        source_hint="sec",
        with_acquire=False,
        skip_assemble=True,
        force=False,
        context=ctx,
        eval_ok=None,
    )

    assert metrics["final_status"]["eval_ok"] is None, (
        f"eval_ok must be null for skip; got {metrics['final_status']['eval_ok']!r}"
    )
    eval_agg = metrics["aggregates"]["evaluate"]
    assert eval_agg.get("skipped") is True, (
        f"evaluate aggregate must be {{skipped: true}}; got {eval_agg!r}"
    )
    assert "score" not in eval_agg, (
        f"evaluate aggregate must not contain 'score' when skipped; got {eval_agg!r}"
    )
